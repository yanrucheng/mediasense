"""Private loopback transport. A runtime handle grants only scoped reads."""

from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import fcntl
import json
import logging
import os
from pathlib import Path
import re
import secrets
import sys
from threading import Thread, Event
from urllib.parse import parse_qs, quote, urlparse

from mediasense.plan._sqlite import RevisionConflict, WorkNotFound, SQLitePlanStore
from mediasense.plan.preview import PreviewError
from mediasense.plan.view import unavailable_view
from mediasense.plan.work import PlanFailure, _decode_cursor
from mediasense.source_sets import SourceSetResolutionError
from ._view_lifecycle import Lifecycle, ViewUnavailable
from ._view_files import (
    PROTOCOL,
    FORMAT,
    open_owned,
    write_header,
    lifecycle_lock,
    remove_connection,
    configure_logging,
    DiagnosticCleanup,
)
from .resources import resource_root

_LOG = logging.getLogger(__name__)


class ViewServer(ThreadingHTTPServer):
    daemon_threads = True

    def __init__(self, build, *, lifecycle=None, root=None):
        super().__init__(("127.0.0.1", 0), Handler)
        self.build, self.secret, self.instance = (
            build,
            secrets.token_urlsafe(32),
            secrets.token_hex(16),
        )
        self.lifecycle = lifecycle or Lifecycle()
        self.routes = self.lifecycle.routes
        self.origin = "http://127.0.0.1:" + str(self.server_port)
        self.closed = Event()
        self.cleanup = DiagnosticCleanup(root) if root else None
        self.interrupted = 0

    def get_request(self):
        request, address = super().get_request()
        request.settimeout(10)
        return request, address

    def health(self):
        return {
            "build": self.build,
            "uid": os.getuid(),
            "pid": os.getpid(),
            "instance": self.instance,
            "protocol": PROTOCOL,
            **self.lifecycle.status(),
        }

    def stop(self, reason):
        self.lifecycle.retire(reason)
        self.interrupted = self.lifecycle.drain()
        if self.interrupted:
            _LOG.warning(
                "Plan view stop interrupted %d in-flight requests", self.interrupted
            )
        self.shutdown()

    def monitor(self):
        try:
            while not self.closed.wait(self.lifecycle.policy.sweep_interval):
                previous = self.lifecycle.evictions
                if self.lifecycle.sweep():
                    self.shutdown()
                    return
                if previous != self.lifecycle.evictions:
                    _LOG.info(
                        "Plan view contexts evicted: %d total", self.lifecycle.evictions
                    )
        except Exception as error:
            self.lifecycle.last_failure = type(error).__name__
            _LOG.error("Plan view monitor failed: %s", type(error).__name__)
            self.lifecycle.retire("operation_failed")
            self.shutdown()
            raise

    def bind(self, value, send=None):
        snapshot = SQLitePlanStore.read_binding(
            Path(value["workspace"]).resolve() / "plan" / "work-v3.sqlite3",
            value["work_ref"],
        )
        result = unavailable_view(
            {**value, "result_ref": snapshot["result_ref"]},
            "view_resource_unavailable",
            "View cannot be read",
        )
        try:
            token = self.lifecycle.register(value)
            with self.lifecycle.request():
                if self.cleanup:
                    self.cleanup.run()
                current = self.origin + "/v/" + token
                result.update(
                    current_uri=current, current_revision=snapshot["revision"]
                )
                if snapshot["revision"] != value["revision"]:
                    result.update(
                        status="superseded",
                        problems=[
                            {
                                "code": "view_superseded",
                                "message": "A newer saved Work revision is current.",
                            }
                        ],
                    )
                else:
                    with self.lifecycle.heavy(
                        token, value["revision"], already_pinned=True
                    ) as view:
                        result = self.project(view, value, result, current)
                        if result["status"] == "unavailable":
                            self.lifecycle.record_failure(result["problems"][0]["code"])
                        if send:
                            send(200, result)
                        return result
                if send:
                    send(200, result)
                return result
        except RevisionConflict as error:
            result.update(
                status="superseded",
                current_revision=error.current_revision,
                problems=[
                    {
                        "code": "view_superseded",
                        "message": "Work changed during delivery.",
                    }
                ],
            )
        except ViewUnavailable as error:
            if error.code == "retiring":
                raise
            self.lifecycle.record_failure(error.code)
            result.update(
                status="unavailable",
                current_uri=None,
                revision_uri=None,
                problems=[{"code": error.code, "message": str(error)}],
            )
        if send:
            send(200, result)
        return result

    def project(self, view, value, result, current):
        try:
            view.overview(value["revision"])
            page = view.page(value["revision"], "groups")
            problems = [
                {
                    "code": "evidence_unavailable",
                    "message": "Prepared preview is unreadable: " + sample["label"],
                    **(
                        {"source_item_ref": sample["source_item_ref"]}
                        if sample["source_item_ref"]
                        else {}
                    ),
                    **(
                        {"evidence_ref": sample["evidence_ref"]}
                        if sample["evidence_ref"]
                        else {}
                    ),
                }
                for item in page["items"]
                for sample in item.get("samples", [])
                if not sample["available"]
            ]
            notes = view.page(value["revision"], "decision_notes")
            selected = list(
                dict.fromkeys(
                    ref
                    for note in notes["items"]
                    for ref in note.get("evidence_refs", [])
                )
            )[:16]
            for ref in selected:
                evidence = view.evidence(value["revision"], ref)
                if evidence.get("error", {}).get("code") == "evidence_unavailable":
                    problems.append(
                        {
                            "code": "evidence_unavailable",
                            "evidence_ref": ref,
                            "message": evidence["error"]["message"],
                        }
                    )
            view._check(value["revision"])
        except RevisionConflict as error:
            result.update(
                status="superseded",
                current_revision=error.current_revision,
                problems=[
                    {
                        "code": "view_superseded",
                        "message": "Work changed during delivery.",
                    }
                ],
            )
        except (PreviewError, PlanFailure, SourceSetResolutionError) as error:
            result["problems"] = [{"code": "result_unavailable", "message": str(error)}]
        except OSError as error:
            result["problems"] = [
                {"code": "view_resource_unavailable", "message": str(error)}
            ]
        else:
            result.update(
                status="degraded" if problems else "ready",
                problems=problems,
                revision_uri=current + "?revision=" + quote(value["revision"], safe=""),
            )
        if result["status"] == "unavailable":
            result.update(current_uri=None, revision_uri=None)
        return result


class Handler(BaseHTTPRequestHandler):
    def log_message(self, *_):
        pass

    def _allowed(self):
        if self.headers.get("Host") != self.server.origin.removeprefix("http://"):
            return False
        origin = self.headers.get("Origin")
        if origin is not None and origin != self.server.origin:
            return False
        if (
            self.command == "GET"
            and self.headers.get("Sec-Fetch-Mode") == "navigate"
            and self.headers.get("Sec-Fetch-Dest") == "document"
            and len(urlparse(self.path).path.strip("/").split("/")) == 2
        ):
            return True
        return self.headers.get("Sec-Fetch-Site") not in {"cross-site", "same-site"}

    def send(self, status, data, content_type="application/json"):
        if not isinstance(data, bytes):
            data = json.dumps(data, ensure_ascii=False).encode()
        self.send_response(status)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(data)))
        self.send_header("Cache-Control", "no-store")
        self.send_header("Referrer-Policy", "no-referrer")
        self.send_header("X-Content-Type-Options", "nosniff")
        self.send_header("Cross-Origin-Resource-Policy", "same-origin")
        self.send_header(
            "Content-Security-Policy",
            "default-src 'none'; script-src 'self'; style-src 'self'; img-src 'self'; connect-src 'self'; base-uri 'none'; frame-ancestors 'none'",
        )
        if status == 503 and isinstance(data, bytes) and b"view_resource_busy" in data:
            self.send_header("Retry-After", "1")
        self.end_headers()
        self.wfile.write(data)

    def body(self, limit):
        if self.headers.get_content_type() != "application/json" or self.headers.get(
            "Transfer-Encoding"
        ):
            raise PlanFailure("invalid_request", "JSON body required")
        try:
            length = int(self.headers.get("Content-Length", "0"))
            if not 0 < length <= limit:
                raise ValueError()
            value = json.loads(self.rfile.read(length))
            if not isinstance(value, dict):
                raise ValueError()
            return value
        except (ValueError, UnicodeError):
            raise PlanFailure("invalid_request", "Invalid bounded JSON body") from None

    def do_POST(self):
        if not self._allowed():
            return self.send(403, {"error": "forbidden"})
        try:
            parts = urlparse(self.path).path.strip("/").split("/")
            if len(parts) == 3 and parts[0] == "v" and parts[2] == "activity":
                if (
                    self.headers.get("Origin") != self.server.origin
                    or parts[1] not in self.server.routes
                ):
                    return self.send(403, {"error": "forbidden"})
                value = self.body(256)
                if (
                    set(value) != {"revision"}
                    or not isinstance(value["revision"], str)
                    or not value["revision"]
                ):
                    raise PlanFailure(
                        "invalid_request", "Only the page revision is accepted"
                    )
                return self.send(
                    200,
                    self.server.lifecycle.current(
                        parts[1], revision=value["revision"], activity=True
                    ),
                )
            if self.headers.get("Authorization") != "Bearer " + self.server.secret:
                return self.send(403, {"error": "forbidden"})
            value = self.body(32768)
            if self.path == "/control/health":
                return self.send(200, self.server.health())
            if self.path == "/control/bind":
                if set(value) != {
                    "workspace",
                    "dataset_ref",
                    "work_ref",
                    "revision",
                } or not all(isinstance(v, str) and v for v in value.values()):
                    raise PlanFailure("invalid_request", "Invalid binding")
                return self.server.bind(value, self.send)
            if self.path == "/control/stop":
                self.server.lifecycle.retire("explicit_stop")
                Thread(
                    target=self.server.stop, args=("explicit_stop",), daemon=True
                ).start()
                return self.send(200, {"stopping": True})
            return self.send(404, {"error": "not found"})
        except Exception as error:
            self.failure(error)

    def failure(self, error, current_uri=None):
        if isinstance(error, (BrokenPipeError, ConnectionResetError, TimeoutError)):
            self.server.lifecycle.last_failure = "client_disconnected"
            return
        if isinstance(error, RevisionConflict):
            status, body = (
                409,
                {
                    "error": "view_superseded",
                    "current_revision": error.current_revision,
                },
            )
        elif isinstance(error, ViewUnavailable):
            status, body = 503, {"error": error.code}
        elif isinstance(error, PlanFailure):
            status = 400 if error.code in {"invalid_request", "invalid_cursor"} else 503
            body = {"error": error.code, "message": str(error)}
        elif isinstance(error, (PreviewError, SourceSetResolutionError, OSError)):
            status, body = (
                503,
                {"error": "view_resource_unavailable", "message": str(error)},
            )
        elif isinstance(error, WorkNotFound):
            status, body = 400, {"error": "invalid_view_request"}
        else:
            self.server.lifecycle.last_failure = "operation_failed"
            _LOG.error("Plan page failed unexpectedly: %s", type(error).__name__)
            status, body = (
                500,
                {
                    "error": "operation_failed",
                    "operation_failed": "Unexpected page failure; saved Work is retained.",
                },
            )
        if current_uri:
            body["current_uri"] = current_uri
        if status >= 500:
            self.server.lifecycle.last_failure = body["error"]
        try:
            self.send(status, body)
        except (BrokenPipeError, ConnectionResetError, TimeoutError):
            self.server.lifecycle.last_failure = "client_disconnected"

    def do_GET(self):
        if not self._allowed():
            return self.send(403, {"error": "forbidden"})
        url = urlparse(self.path)
        parts = url.path.strip("/").split("/")
        if (
            len(parts) not in {2, 3}
            or parts[0] != "v"
            or parts[1] not in self.server.routes
        ):
            return self.send(404, {"error": "unknown view"})
        token = parts[1]
        route = self.server.routes[token]
        current_uri = self.server.origin + "/v/" + token
        query = parse_qs(url.query, keep_blank_values=True)

        def parameter(name, required=True):
            values = query.get(name)
            if values is None and not required:
                return None
            if values is None or len(values) != 1 or not values[0]:
                raise PlanFailure(
                    "invalid_request", "One " + name + " value is required"
                )
            return values[0]

        try:
            if len(parts) == 2:
                revision = parameter("revision", False)
                try:
                    self.server.lifecycle.current(token, revision=revision)
                except RevisionConflict:
                    # Deliver the shell so the exact-page adapter can explain
                    # its 409 overview. This stale navigation never renews use.
                    return self.send(
                        200,
                        (resource_root() / "plan-view" / "index.html")
                        .read_text()
                        .replace("__VIEW_BASE__", "/v/" + token)
                        .encode(),
                        "text/html; charset=utf-8",
                    )
                with self.server.lifecycle.request():
                    return self.send(
                        200,
                        (resource_root() / "plan-view" / "index.html")
                        .read_text()
                        .replace("__VIEW_BASE__", "/v/" + token)
                        .encode(),
                        "text/html; charset=utf-8",
                    )
            action = parts[2]
            if action in {"app.js", "style.css"}:
                return self.send(
                    200,
                    (resource_root() / "plan-view" / action).read_bytes(),
                    "text/javascript; charset=utf-8"
                    if action.endswith("js")
                    else "text/css; charset=utf-8",
                )
            if action == "current":
                return self.send(200, self.server.lifecycle.current(token))
            if action not in {"overview", "page", "evidence", "asset"}:
                return self.send(404, {"error": "unknown operation"})
            revision = (
                parameter("revision", action != "overview")
                or route.current()["revision"]
            )
            # Reject stale/invalid reads before acquiring any heavy slot.
            self.server.lifecycle.current(token, revision=revision)
            if action == "page":
                collection = parameter("collection")
                if (
                    re.fullmatch(
                        r"groups|other_outcomes|decision_notes|unassigned|(?:group|outcome|note):[0-9]+",
                        collection,
                    )
                    is None
                ):
                    raise PlanFailure("invalid_request", "Unknown collection")
                cursor = parameter("cursor", False)
                if cursor:
                    _decode_cursor(
                        cursor,
                        work_ref=route.work_ref,
                        revision=revision,
                        collection=collection,
                        requested_limit=50,
                        signing_key=SQLitePlanStore(
                            route.database, readonly=True
                        ).cursor_signing_key(),
                    )
            elif action in {"evidence", "asset"}:
                ref = parameter("ref")
            with self.server.lifecycle.heavy(
                token, revision, on_error=lambda error: self.failure(error, current_uri)
            ) as view:
                if action == "overview":
                    return self.send(200, view.overview(revision))
                if action == "page":
                    return self.send(200, view.page(revision, collection, cursor))
                if action == "evidence":
                    return self.send(200, view.evidence(revision, ref))
                data, suffix = view.asset(revision, ref)
                types = {
                    ".jpg": "image/jpeg",
                    ".jpeg": "image/jpeg",
                    ".png": "image/png",
                    ".webp": "image/webp",
                    ".gif": "image/gif",
                }
                try:
                    return self.send(
                        200, data, types.get(suffix, "application/octet-stream")
                    )
                finally:
                    data = None  # Release response bytes before the heavy pin.
        except Exception as error:
            self.failure(error, current_uri)


def main():
    root, build = Path(sys.argv[1]), sys.argv[2]
    os.umask(0o077)
    with open_owned(root / "process.lock", create=True) as owner:
        fcntl.flock(owner, fcntl.LOCK_EX | fcntl.LOCK_NB)
        handler = configure_logging(root)
        instance = secrets.token_hex(16)
        header = {
            "format": FORMAT,
            "protocol": PROTOCOL,
            "build": build,
            "uid": os.getuid(),
            "pid": os.getpid(),
            "instance": instance,
        }
        write_header(owner, header)
        try:
            server = ViewServer(build, root=root)
        except Exception as error:
            _LOG.error("Plan view startup failed: %s", type(error).__name__)
            write_header(owner, {**header, "exit_reason": "startup_failed"})
            handler.close()
            raise
        server.instance = instance
        temporary = root / (server.instance + ".tmp")
        try:
            with open_owned(temporary, create=True) as stream:
                json.dump(
                    {**header, "origin": server.origin, "secret": server.secret}, stream
                )
            temporary.replace(root / "connection.json")
            _LOG.info(
                "Plan view started instance=%s pid=%d", server.instance, os.getpid()
            )
            Thread(target=server.monitor, daemon=True).start()
            server.serve_forever(poll_interval=0.1)
        finally:
            server.closed.set()
            server.server_close()
            server.cleanup.close()
            server.lifecycle.clear()
            reason = server.lifecycle.reason or "unexpected_exit"
            _LOG.info(
                "Plan view exited reason=%s evictions=%d interrupted=%d",
                reason,
                server.lifecycle.evictions,
                server.interrupted,
            )
            with lifecycle_lock(root):
                remove_connection(root, server.instance)
                temporary.unlink(missing_ok=True)
                write_header(
                    owner,
                    {
                        **header,
                        "exit_reason": reason,
                        "interrupted_requests": server.interrupted,
                    },
                )
            handler.close()


if __name__ == "__main__":
    main()
