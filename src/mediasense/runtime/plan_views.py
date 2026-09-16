"""Installation/user-scoped lifecycle for the read-only local Plan view process."""

from functools import lru_cache
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys
import time
from urllib.error import URLError, HTTPError
from urllib.parse import urlsplit
from urllib.request import Request, build_opener, ProxyHandler

from mediasense.plan.view import unavailable_view
from ._view_files import (
    PROTOCOL,
    lifecycle_lock,
    private_directory,
    process_state,
    read_json,
)


@lru_cache(maxsize=1)
def build_identity():
    root = Path(__file__).resolve().parents[1]
    digest = hashlib.sha256((str(root) + sys.executable + sys.version).encode())
    for path in sorted(root.rglob("*")):
        if path.is_file() and "__pycache__" not in path.parts:
            digest.update(str(path.relative_to(root)).encode())
            digest.update(path.read_bytes())
    return digest.hexdigest()


def runtime_directory(*, create=True):
    from .dataset import default_local_dataset_root

    root = (
        default_local_dataset_root().parent
        / "runtime"
        / "plan-views"
        / build_identity()
    )
    if create:
        private_directory(root.parent, create=True)
        private_directory(root, create=True)
    return root


class Retiring(OSError):
    pass


def rpc(info, action, value=None, *, timeout=60):
    request = Request(
        info["origin"] + "/control/" + action,
        data=json.dumps(value or {}).encode(),
        headers={
            "Content-Type": "application/json",
            "Authorization": "Bearer " + info["secret"],
        },
    )
    try:
        with build_opener(ProxyHandler({})).open(
            request, timeout=max(0.001, timeout)
        ) as response:
            result = json.load(response)
    except HTTPError as error:
        with error:
            value = json.load(error)
        if value.get("error") == "retiring":
            raise Retiring("Plan view host is retiring") from error
        if value.get("operation_failed"):
            raise RuntimeError(value["operation_failed"]) from error
        raise
    if result.get("operation_failed"):
        raise RuntimeError(result["operation_failed"])
    return result


def _info(root, *, timeout=1):
    try:
        value = read_json(root / "connection.json")
        origin = urlsplit(value["origin"])
        if (
            origin.scheme != "http"
            or origin.hostname != "127.0.0.1"
            or not origin.port
            or origin.username
            or origin.password
            or origin.path
            or origin.query
            or origin.fragment
            or value.get("protocol") != PROTOCOL
        ):
            return None
        healthy = rpc(value, "health", timeout=min(1, timeout))
        if (
            healthy.get("build") == build_identity() == value.get("build")
            and healthy.get("uid") == os.getuid() == value.get("uid")
            and healthy.get("instance") == value.get("instance")
            and healthy.get("pid") == value.get("pid")
            and healthy.get("protocol") == PROTOCOL
        ):
            return value | {"health": healthy}
    except (OSError, URLError, ValueError, KeyError):
        pass
    return None


def ensure_host(*, deadline=None, retiring_instance=None):
    deadline = deadline or time.monotonic() + 60
    root = runtime_directory()
    while time.monotonic() < deadline:
        with lifecycle_lock(root, deadline=deadline):
            info = _info(root, timeout=max(0.001, deadline - time.monotonic()))
            if info and info["health"]["lifecycle"] == "accepting":
                return info
            ownership, owner = process_state(root)
            if ownership == "held":
                if (not info or info["health"]["lifecycle"] != "draining") and not (
                    retiring_instance and owner.get("instance") == retiring_instance
                ):
                    raise OSError(
                        "Plan view process owns its lifetime lock but is unreachable"
                    )
                # Release parent lock before waiting for the old instance cleanup.
            elif ownership == "unknown":
                raise OSError("Cannot verify Plan view process ownership")
            else:
                process = subprocess.Popen(
                    [
                        sys.executable,
                        "-m",
                        "mediasense.runtime._view_server",
                        str(root),
                        build_identity(),
                    ],
                    stdin=subprocess.DEVNULL,
                    stdout=subprocess.DEVNULL,
                    stderr=subprocess.DEVNULL,
                    start_new_session=True,
                    close_fds=True,
                )
                startup_deadline = min(deadline, time.monotonic() + 15)
                while time.monotonic() < startup_deadline:
                    if process.poll() is not None:
                        raise OSError(
                            "Plan view host exited during startup; see "
                            + str(root / "host.log")
                        )
                    info = _info(
                        root, timeout=max(0.001, startup_deadline - time.monotonic())
                    )
                    if info:
                        return info
                    time.sleep(0.05)
                # Never kill a possibly published/working instance on an RPC deadline.
                raise TimeoutError(
                    "Plan view host did not become ready within startup deadline"
                )
        time.sleep(min(0.05, max(0, deadline - time.monotonic())))
    raise TimeoutError("Plan view delivery deadline exceeded")


def _retryable(error):
    reason = error.reason if isinstance(error, URLError) else error
    return isinstance(reason, (Retiring, ConnectionRefusedError))


def deliver(opened, receipt):
    deadline = time.monotonic() + 60
    retiring_instance = None
    for attempt in range(2):
        try:
            info = ensure_host(deadline=deadline, retiring_instance=retiring_instance)
            remaining = deadline - time.monotonic()
            if remaining <= 0:
                raise TimeoutError("Plan view delivery deadline exceeded")
            return rpc(
                info,
                "bind",
                {
                    "workspace": str(opened.workspace),
                    "dataset_ref": opened.manifest.dataset_ref,
                    "work_ref": receipt["work_ref"],
                    "revision": receipt["revision"],
                },
                timeout=remaining,
            )
        except (OSError, URLError) as error:
            if attempt == 0 and _retryable(error) and time.monotonic() < deadline:
                if isinstance(error, Retiring):
                    retiring_instance = info["instance"]
                continue
            return unavailable_view(receipt, "view_service_unavailable", str(error))


def control(action):
    root = runtime_directory(create=False)
    if not root.exists():
        return {"state": "stopped", "build": build_identity(), "exit_reason": None}
    private_directory(root.parent)
    private_directory(root)
    with lifecycle_lock(root, deadline=time.monotonic() + 5):
        info = _info(root)
        ownership, header = process_state(root)
        if info is None:
            proven = ownership == "released" or (
                ownership == "absent" and not (root / "connection.json").exists()
            )
            return {
                "state": "stopped" if proven else "unknown/unreachable",
                "build": build_identity(),
                "instance": header.get("instance"),
                "pid": header.get("pid"),
                "exit_reason": header.get("exit_reason"),
                "diagnostics": str(root / "host.log"),
            }
        if action != "stop":
            return {
                "state": "running"
                if info["health"]["lifecycle"] == "accepting"
                else "draining",
                **info["health"],
                "diagnostics": str(root / "host.log"),
            }
    # Do not hold the parent lock while stop drains or finally removes connection.
    try:
        rpc(info, "stop", timeout=1)
    except (OSError, URLError):
        pass  # Verify the actual instance below; port failure proves nothing.
    deadline = time.monotonic() + 7
    while time.monotonic() < deadline:
        with lifecycle_lock(root, deadline=deadline):
            ownership, header = process_state(root)
            if ownership == "released" and header.get("instance") == info["instance"]:
                return {
                    "state": "stopped",
                    "build": build_identity(),
                    "instance": info["instance"],
                    "pid": info["pid"],
                    "exit_verified": True,
                    "exit_reason": header.get("exit_reason"),
                    "interrupted_requests": header.get("interrupted_requests", 0),
                }
        time.sleep(0.05)
    return {
        "state": "unknown/unreachable",
        "build": build_identity(),
        "instance": info["instance"],
        "exit_verified": False,
        "problem": "Bounded exit verification did not complete",
    }
