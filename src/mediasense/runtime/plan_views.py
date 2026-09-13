"""Installation/user-scoped lifecycle for the read-only local Plan view process."""

from __future__ import annotations

from contextlib import contextmanager
from functools import lru_cache
import fcntl
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys
import time
from urllib.error import URLError, HTTPError
from urllib.request import Request, build_opener, ProxyHandler

from mediasense.plan.view import unavailable_view


@lru_cache(maxsize=1)
def build_identity():
    root = Path(__file__).resolve().parents[1]
    digest = hashlib.sha256((str(root) + sys.executable + sys.version).encode())
    for path in sorted(root.rglob("*")):
        if path.is_file() and "__pycache__" not in path.parts:
            digest.update(str(path.relative_to(root)).encode())
            digest.update(path.read_bytes())
    return digest.hexdigest()


def runtime_directory():
    from .dataset import default_local_dataset_root

    root = (
        default_local_dataset_root().parent
        / "runtime"
        / "plan-views"
        / build_identity()
    )
    root.mkdir(parents=True, exist_ok=True, mode=0o700)
    root.chmod(0o700)
    return root


def rpc(info, action, value=None):
    request = Request(
        info["origin"] + "/control/" + action,
        data=json.dumps(value or {}).encode(),
        headers={
            "Content-Type": "application/json",
            "Authorization": "Bearer " + info["secret"],
        },
    )
    try:
        with build_opener(ProxyHandler({})).open(request, timeout=60) as response:
            result = json.load(response)
    except HTTPError as error:
        value = json.load(error)
        if value.get("operation_failed"):
            raise RuntimeError(value["operation_failed"]) from error
        raise
    if result.get("operation_failed"):
        raise RuntimeError(result["operation_failed"])
    return result


@contextmanager
def _lifecycle_lock(root):
    with (root / "launch.lock").open("a") as stream:
        fcntl.flock(stream, fcntl.LOCK_EX)
        yield


def _info(root):
    try:
        value = json.loads((root / "connection.json").read_text())
        # Never contact a remotely substituted origin.
        if not value["origin"].startswith("http://127.0.0.1:"):
            return None
        healthy = rpc(value, "health")
        if (
            healthy.get("build") == build_identity()
            and healthy.get("uid") == os.getuid()
            and healthy.get("instance") == value.get("instance")
        ):
            return value
    except (OSError, URLError, ValueError, KeyError):
        pass
    return None


def ensure_host():
    root = runtime_directory()
    with _lifecycle_lock(root):
        info = _info(root)
        if info:
            return info
        with (root / "host.log").open("ab") as log:
            process = subprocess.Popen(
                [
                    sys.executable,
                    "-m",
                    "mediasense.runtime._view_server",
                    str(root),
                    build_identity(),
                ],
                stdin=subprocess.DEVNULL,
                stdout=log,
                stderr=log,
                start_new_session=True,
                close_fds=True,
            )
        deadline = time.monotonic() + 15
        while time.monotonic() < deadline:
            if process.poll() is not None:
                raise OSError(
                    "Plan view host exited during startup; see "
                    + str(root / "host.log")
                )
            info = _info(root)
            if info:
                return info
            time.sleep(0.05)
        process.terminate()
        raise OSError("Plan view host did not become ready within 15 seconds")


def deliver(opened, receipt):
    try:
        info = ensure_host()
        return rpc(
            info,
            "bind",
            {
                "workspace": str(opened.workspace),
                "dataset_ref": opened.manifest.dataset_ref,
                "work_ref": receipt["work_ref"],
                "revision": receipt["revision"],
            },
        )
    except (OSError, URLError) as error:
        return unavailable_view(receipt, "view_service_unavailable", str(error))


def control(action):
    root = runtime_directory()
    with _lifecycle_lock(root):
        info = _info(root)
        if info is None:
            return {"state": "stopped", "build": build_identity()}
        result = rpc(info, "stop" if action == "stop" else "health")
        if action == "stop":
            for _ in range(100):
                if _info(root) is None:
                    return {"state": "stopped", "build": build_identity()}
                time.sleep(0.05)
            raise OSError("View host has not stopped")
        return {"state": "running", **result}
