"""Private in-memory admission and disposable projections owned by ViewServer."""

from contextlib import contextmanager
from dataclasses import dataclass, field
import json
import math
from pathlib import Path
import secrets
from threading import Condition, RLock
import time
import traceback

from mediasense.plan import PlanWorkTool
from mediasense.plan._sqlite import SQLitePlanStore, RevisionConflict
from mediasense.plan.view import PlanView
from mediasense.precheck.read import PrecheckReadTool, bind_precheck_read


@dataclass(frozen=True)
class Policy:
    cache_idle: float = 60 * 60
    service_idle: float = 72 * 60 * 60
    sweep_interval: float = 5
    contexts: int = 2
    routes: int = 256
    wait_seconds: float = 5
    waiters: int = 16
    drain_seconds: float = 5


class ViewUnavailable(Exception):
    def __init__(self, code):
        self.code = code
        super().__init__(code)


@dataclass
class Route:
    workspace: Path
    dataset_ref: str
    work_ref: str
    result_ref: str
    identity: tuple
    lock: RLock = field(default_factory=RLock)

    @property
    def database(self):
        return self.workspace / "plan" / "work-v3.sqlite3"

    def current(self):
        if self.identity != binding_identity(self.workspace):
            raise ViewUnavailable("view_resource_unavailable")
        if (
            json.loads((self.workspace / "dataset.json").read_text())["dataset_ref"]
            != self.dataset_ref
        ):
            raise ViewUnavailable("view_resource_unavailable")
        value = SQLitePlanStore.read_binding(self.database, self.work_ref)
        if value["result_ref"] != self.result_ref:
            raise ViewUnavailable("view_resource_unavailable")
        return value


def binding_identity(workspace):
    # Exact physical binding. Do not fold case or follow a replaced workspace.
    return tuple(
        (s.st_dev, s.st_ino)
        for s in (
            p.stat()
            for p in (
                workspace,
                workspace / "plan" / "work-v3.sqlite3",
                workspace / "precheck" / "work.sqlite3",
            )
        )
    )


def construct_view(route):
    reader = PrecheckReadTool(route.workspace / "precheck" / "work.sqlite3")
    tool = PlanWorkTool(
        route.workspace / "plan",
        bind_precheck_read(reader, route.dataset_ref),
        readonly=True,
    )
    return PlanView(tool, route.work_ref)


class Lifecycle:
    def __init__(
        self, *, policy=Policy(), clock=time.monotonic, factory=construct_view
    ):
        self.policy, self.clock, self.factory = policy, clock, factory
        self.condition = Condition(RLock())
        self.routes, self.bindings, self.contexts = {}, {}, {}
        self.active = set()
        self.inflight = self.waiters = self.evictions = 0
        self.accepting = True
        self.last_use = clock()
        self.last_read = {}
        self.context_bindings = {}
        self.reason = self.last_failure = None

    def register(self, value):
        workspace = Path(value["workspace"]).resolve(strict=True)
        dataset = value["dataset_ref"]
        if (
            json.loads((workspace / "dataset.json").read_text())["dataset_ref"]
            != dataset
        ):
            raise ViewUnavailable("view_resource_unavailable")
        current = SQLitePlanStore.read_binding(
            workspace / "plan" / "work-v3.sqlite3", value["work_ref"]
        )
        identity = binding_identity(workspace)
        key = (str(workspace), identity, dataset, value["work_ref"])
        with self.condition:
            self._accept()
            token = self.bindings.get(key)
            if token is None:
                if len(self.routes) >= self.policy.routes:
                    raise ViewUnavailable("view_capacity_exceeded")
                token = secrets.token_urlsafe(32)
                self.routes[token] = Route(
                    workspace,
                    dataset,
                    value["work_ref"],
                    current["result_ref"],
                    identity,
                )
                self.bindings[key] = token
            return token

    def _accept(self):
        if not self.accepting:
            raise ViewUnavailable("retiring")

    def record_failure(self, code):
        with self.condition:
            self.last_failure = code

    def status(self):
        with self.condition:
            idle = max(0, self.clock() - self.last_use)
            return {
                "lifecycle": "accepting" if self.accepting else "draining",
                "routes": len(self.routes),
                "contexts": len(self.contexts),
                "active_heavy_requests": len(self.active),
                "inflight": self.inflight,
                "waiters": self.waiters,
                "limits": vars(self.policy),
                "idle_seconds": idle,
                "idle_remaining_seconds": max(
                    0, math.ceil(self.policy.service_idle - idle)
                ),
                "evictions": self.evictions,
                "exit_reason": self.reason,
                "last_failure": self.last_failure,
            }

    def current(self, token, *, revision=None, activity=False):
        value = self.routes[token].current()
        with self.condition:
            self._accept()
            if revision is not None and value["revision"] != revision:
                raise RevisionConflict(value["revision"])
            if activity:
                self.last_use = self.clock()
            return {k: value[k] for k in ("revision", "state")} | {
                "idle_remaining_seconds": self.status()["idle_remaining_seconds"]
            }

    @contextmanager
    def request(self):
        """Validated lightweight content/bind pin, held through response sending."""
        with self.condition:
            self._accept()
            self.inflight += 1
        try:
            yield
        finally:
            with self.condition:
                self.inflight -= 1
                self.last_use = self.clock()
                self.condition.notify_all()

    def _drop(self, token):
        view = self.contexts.pop(token)
        if view is not None:
            view.close()
        self.context_bindings.pop(token, None)
        self.last_read.pop(token, None)
        self.evictions += 1

    @contextmanager
    def heavy(self, token, revision, *, on_error=None, already_pinned=False):
        route = self.routes[token]
        initial = route.current()
        if initial["revision"] != revision:
            raise RevisionConflict(initial["revision"])
        deadline = time.monotonic() + self.policy.wait_seconds
        waiting = False
        with self.condition:
            try:
                while True:
                    self._accept()
                    available = (
                        token not in self.active
                        and len(self.active) < self.policy.contexts
                    )
                    if available:
                        if (
                            token not in self.contexts
                            and len(self.contexts) >= self.policy.contexts
                        ):
                            victims = self.contexts.keys() - self.active
                            if victims:
                                self._drop(
                                    min(victims, key=lambda t: self.last_read[t])
                                )
                        if (
                            token in self.contexts
                            or len(self.contexts) < self.policy.contexts
                        ):
                            break
                    if not waiting:
                        if self.waiters >= self.policy.waiters:
                            raise ViewUnavailable("view_resource_busy")
                        self.waiters += 1
                        waiting = True
                    remaining = deadline - time.monotonic()
                    if remaining <= 0:
                        raise ViewUnavailable("view_resource_busy")
                    self.condition.wait(remaining)
                self.active.add(token)
                if not already_pinned:
                    self.inflight += 1
                self.contexts.setdefault(token, None)  # Construction consumes capacity.
            finally:
                if waiting:
                    self.waiters -= 1
        view = None
        failed = False
        entered = False
        try:
            with route.lock:
                current = route.current()
                if current["revision"] != revision:
                    raise RevisionConflict(current["revision"])
                binding = tuple(
                    current[k] for k in ("revision", "state", "published_path")
                )
                view = self.contexts[token]
                if view is not None and self.context_bindings[token] != binding:
                    view.close()
                    view = self.contexts[token] = None
                if view is None:
                    view = self.factory(route)
                    self.contexts[token] = view
                    self.context_bindings[token] = binding
                entered = True
                yield view
        except BaseException as error:
            failed = True
            # Failed factory/projection frames can retain a Reader independently
            # of PlanView. Keep the traceback locations, release dead frame locals
            # before declaring this slot free (including chained exceptions).
            seen = set()
            pending = [error]
            while pending:
                cause = pending.pop()
                if id(cause) in seen:
                    continue
                seen.add(id(cause))
                traceback.clear_frames(cause.__traceback__)
                pending.extend(
                    e for e in (cause.__cause__, cause.__context__) if e is not None
                )
            if not entered or on_error is None or not isinstance(error, Exception):
                raise
            on_error(error)
        finally:
            # No Work lock while reacquiring admission. Drop the entire Reader
            # graph on failure, including references in the caller's view handle.
            view = None
            with self.condition:
                if failed:
                    self._drop(token)
                else:
                    self.last_read[token] = self.clock()
                self.active.remove(token)
                if not already_pinned:
                    self.inflight -= 1
                self.last_use = self.clock()
                self.condition.notify_all()

    def sweep(self):
        with self.condition:
            now = self.clock()
            for token in list(self.contexts.keys() - self.active):
                if now - self.last_read[token] >= self.policy.cache_idle:
                    self._drop(token)
            if (
                self.accepting
                and not self.inflight
                and now - self.last_use >= self.policy.service_idle
            ):
                self.retire("idle_timeout")
                return True
            return False

    def retire(self, reason):
        with self.condition:
            self.accepting = False
            self.reason = self.reason or reason
            self.condition.notify_all()

    def drain(self):
        deadline = time.monotonic() + self.policy.drain_seconds
        with self.condition:
            while self.inflight and time.monotonic() < deadline:
                self.condition.wait(max(0, deadline - time.monotonic()))
            return self.inflight

    def clear(self):
        with self.condition:
            for token in list(self.contexts.keys() - self.active):
                self._drop(token)
