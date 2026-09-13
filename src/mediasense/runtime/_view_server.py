"""Private loopback transport. A runtime handle grants only scoped reads."""

from __future__ import annotations

from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import json
import logging
import os
from pathlib import Path
import secrets
import sys
from threading import Thread, RLock
from urllib.parse import parse_qs, quote, urlparse

from mediasense.plan import PlanWorkTool
from mediasense.plan._sqlite import RevisionConflict, WorkNotFound
from mediasense.plan.preview import PreviewError
from mediasense.plan.view import PlanView, unavailable_view
from mediasense.plan.work import PlanFailure
from mediasense.precheck.read import PrecheckReadTool, bind_precheck_read
from mediasense.source_sets import SourceSetResolutionError
from .resources import resource_root

_LOG = logging.getLogger(__name__)


class ViewServer(ThreadingHTTPServer):
    daemon_threads = True

    def __init__(self, build):
        super().__init__(("127.0.0.1", 0), Handler)
        self.build, self.secret, self.instance = (
            build,
            secrets.token_urlsafe(32),
            secrets.token_hex(16),
        )
        self.routes, self.bindings, self.lock = {}, {}, RLock()
        self.origin = "http://127.0.0.1:" + str(self.server_port)

    def bind(self, value):
        workspace = Path(value["workspace"]).resolve()
        manifest = json.loads((workspace / "dataset.json").read_text())
        if manifest["dataset_ref"] != value["dataset_ref"]:
            raise ValueError("Dataset binding mismatch")
        key = (str(workspace), value["dataset_ref"], value["work_ref"])
        with self.lock:
            token = self.bindings.get(key)
            if token is None:
                tool = PlanWorkTool(
                    workspace / "plan",
                    bind_precheck_read(
                        PrecheckReadTool(workspace / "precheck" / "work.sqlite3"),
                        value["dataset_ref"],
                    ),
                )
                view = PlanView(tool, value["work_ref"])
                view.current()  # Refuse an unknown Work before registering.
                token = secrets.token_urlsafe(32)
                self.bindings[key], self.routes[token] = token, view
            view = self.routes[token]
        snapshot = view.current()
        receipt = {**value, "result_ref": snapshot.result_ref}
        result = unavailable_view(
            receipt, "view_resource_unavailable", "View cannot be read"
        )
        current = self.origin + "/v/" + token
        result.update(current_uri=current, current_revision=snapshot.revision)
        if snapshot.revision != value["revision"]:
            result.update(
                status="superseded",
                problems=[
                    {
                        "code": "view_superseded",
                        "message": "A newer saved Work revision is current.",
                    }
                ],
            )
            return result
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
        return result


class Handler(BaseHTTPRequestHandler):
    def log_message(self, *_):
        pass  # Avoid recording bearer-like route handles in request logs.

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
        self.end_headers()
        self.wfile.write(data)

    def do_POST(self):
        if (
            not self._allowed()
            or self.headers.get("Authorization") != "Bearer " + self.server.secret
        ):
            return self.send(403, {"error": "forbidden"})
        action = self.path.removeprefix("/control/")
        try:
            length = int(self.headers.get("Content-Length", "0"))
            if not 0 <= length <= 32768:
                return self.send(413, {"error": "request too large"})
            value = json.loads(self.rfile.read(length))
            if action == "health":
                result = {
                    "build": self.server.build,
                    "uid": os.getuid(),
                    "pid": os.getpid(),
                    "instance": self.server.instance,
                }
            elif action == "bind":
                result = self.server.bind(value)
            elif action == "stop":
                result = {"stopping": True}
                Thread(target=self.server.shutdown, daemon=True).start()
            else:
                return self.send(404, {"error": "not found"})
            self.send(200, result)
        except Exception as error:
            _LOG.exception("Plan view control operation failed")
            self.send(500, {"operation_failed": str(error) or type(error).__name__})

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
        view = self.server.routes[parts[1]]
        query = parse_qs(url.query)
        current_uri = self.server.origin + "/v/" + parts[1]

        def required_query(name):
            values = query.get(name)
            if values is None or len(values) != 1 or not values[0]:
                raise PlanFailure("invalid_request", f"One {name} value is required")
            return values[0]

        try:
            if len(parts) == 2:
                return self.send(
                    200,
                    (resource_root() / "plan-view" / "index.html")
                    .read_text()
                    .replace("__VIEW_BASE__", "/v/" + parts[1])
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
            revision = query.get("revision", [None])[0]
            if action == "current":
                snapshot = view.current()
                return self.send(
                    200, {"revision": snapshot.revision, "state": snapshot.state}
                )
            if action == "overview":
                revision = revision or view.current().revision
                return self.send(200, view.overview(revision))
            if revision is None:
                raise PlanFailure("invalid_request", "An exact revision is required")
            if action == "page":
                return self.send(
                    200,
                    view.page(
                        revision,
                        required_query("collection"),
                        query.get("cursor", [None])[0],
                    ),
                )
            if action == "evidence":
                return self.send(200, view.evidence(revision, required_query("ref")))
            if action == "asset":
                data, suffix = view.asset(revision, required_query("ref"))
                types = {
                    ".jpg": "image/jpeg",
                    ".jpeg": "image/jpeg",
                    ".png": "image/png",
                    ".webp": "image/webp",
                    ".gif": "image/gif",
                }
                return self.send(
                    200, data, types.get(suffix, "application/octet-stream")
                )
            self.send(404, {"error": "unknown operation"})
        except RevisionConflict as error:
            self.send(
                409,
                {
                    "error": "view_superseded",
                    "current_revision": error.current_revision,
                    "current_uri": current_uri,
                },
            )
        except PlanFailure as error:
            status = 400 if error.code in {"invalid_request", "invalid_cursor"} else 503
            self.send(
                status,
                {
                    "error": error.code,
                    "message": str(error),
                    "current_uri": current_uri,
                },
            )
        except (PreviewError, SourceSetResolutionError, OSError) as error:
            self.send(
                503,
                {
                    "error": "view_resource_unavailable",
                    "message": str(error),
                    "current_uri": current_uri,
                },
            )
        except WorkNotFound as error:
            self.send(400, {"error": "invalid_view_request", "message": str(error)})
        except Exception:
            _LOG.exception("Plan page failed unexpectedly")
            self.send(
                500,
                {
                    "error": "operation_failed",
                    "message": "Unexpected page failure; saved Work is retained.",
                },
            )


def main():
    root, build = Path(sys.argv[1]), sys.argv[2]
    server = ViewServer(build)
    info = {
        "origin": server.origin,
        "secret": server.secret,
        "instance": server.instance,
    }
    temporary = root / (server.instance + ".tmp")
    temporary.write_text(json.dumps(info))
    temporary.chmod(0o600)
    temporary.replace(root / "connection.json")
    try:
        server.serve_forever(poll_interval=0.1)
    finally:
        server.server_close()
        if (
            json.loads((root / "connection.json").read_text()).get("instance")
            == server.instance
        ):
            (root / "connection.json").unlink(missing_ok=True)


if __name__ == "__main__":
    main()
