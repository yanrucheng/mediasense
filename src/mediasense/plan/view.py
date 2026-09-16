"""Regenerable, revision-bound Plan projection over Work and public Result reads."""

from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
import re
from threading import RLock
from urllib.parse import unquote, urlparse

from ._candidate import _PlanResultResolver
from ._sqlite import RevisionConflict
from .preview import PlanPreviewRenderer, PreviewError, _default_asset_resolver
from .work import PlanFailure, _decode_cursor, _encode_cursor, _scope_summary


class ViewDeliveryFailure(RuntimeError):
    def __init__(self, receipt):
        super().__init__(
            "Unexpected view delivery failure; authoritative operation retained"
        )
        self.receipt = receipt


def unavailable_view(receipt, code, message):
    return {
        "work_ref": receipt["work_ref"],
        "result_ref": receipt["result_ref"],
        "revision": receipt["revision"],
        "current_revision": None,
        "observed_at": datetime.now(timezone.utc).isoformat(),
        "current_uri": None,
        "revision_uri": None,
        "status": "unavailable",
        "problems": [{"code": code, "message": message}],
    }


class PlanView:
    """One disposable projection per Work; never accepts business writes."""

    def __init__(self, tool, work_ref):
        self.tool, self.work_ref = tool, work_ref
        self.renderer = PlanPreviewRenderer(tool)
        self.lock = RLock()
        self._binding = None
        self.analysis = None
        self.resolver = None
        self.members = {}
        self.source_details = set()
        self.directory_totals = {}

    def current(self):
        return self.tool.store.snapshot(self.work_ref)

    def close(self):
        """Release the whole projection, including the Reader captured by its boundary."""
        self.analysis = self.resolver = self.renderer = self.tool = None
        self.members.clear()
        self.source_details.clear()
        self.directory_totals.clear()
        self._binding = None

    def _load(self, revision):
        snapshot = self.current()
        if snapshot.revision != revision:
            raise RevisionConflict(snapshot.revision)
        result = self.renderer._read(
            {
                "action": "review",
                "result_ref": snapshot.result_ref,
                "page": {"limit": 1},
            }
        )["result"]
        if result["readiness"] != "plan_ready":
            raise PreviewError("Bound Result is not plan-ready")
        binding = (snapshot.revision, snapshot.state, snapshot.published_path)
        if self._binding != binding:
            snapshot, self.analysis = self.tool.snapshot_for_preview(
                self.work_ref, revision
            )
            self.resolver = _PlanResultResolver(
                snapshot.result_ref, self.tool.precheck_read
            )
            self.members = {}
            self.source_details = set()
            self.directory_totals = {}
            if self.analysis:
                self.resolver.source_views.update(self.analysis.source_views)
                assigned = set()
                for prefix, groups in (
                    ("group", self.analysis.group_members),
                    ("outcome", self.analysis.outcome_members),
                ):
                    for index, refs in enumerate(groups):
                        self.members[f"{prefix}:{index}"] = self._sort(refs)
                        assigned.update(refs)
                self.members["unassigned"] = self._sort(
                    set(self.analysis.scope_members) - assigned
                )
                for group, members in zip(
                    snapshot.candidate["groups"],
                    self.analysis.group_members,
                    strict=True,
                ):
                    path = tuple(group["relative_path"])
                    for depth in range(len(path) + 1):
                        prefix = path[:depth]
                        self.directory_totals[prefix] = self.directory_totals.get(
                            prefix, 0
                        ) + len(members)
            self._binding = binding
        self._check(revision)
        return snapshot, result

    def _sort(self, refs):
        def key(ref):
            locator = self.resolver.source_views.get(ref, {}).get("locator", {})
            return (locator.get("value", ""), ref)

        return tuple(sorted(refs, key=key))

    def _check(self, revision):
        current = self.tool.store.read_binding(
            self.tool.store.database_path, self.work_ref
        )
        if current["revision"] != revision:
            raise RevisionConflict(current["revision"])

    def _member_details(self, result_ref, refs):
        missing = [ref for ref in refs if ref not in self.source_details]
        for offset in range(0, len(missing), 16):
            selection = missing[offset : offset + 16]
            request = {
                "action": "expand",
                "result_ref": result_ref,
                "source_item_refs": selection,
                "include": ["source_item", "observations"],
            }
            seen = set()
            while True:
                response = self.renderer._read(request)
                for item in response["items"]:
                    ref = item["source_item_ref"]
                    if ref not in selection or ref in seen:
                        raise PreviewError(
                            "Member detail response changed its selection"
                        )
                    included = item.get("included", {})
                    if "source_item" not in included or "observations" not in included:
                        raise PreviewError("Member source information is unavailable")
                    self.resolver.source_views[ref] = {
                        **included["source_item"],
                        "observations": included["observations"],
                    }
                    seen.add(ref)
                cursor = response["page"]["next_cursor"]
                if cursor is None:
                    if seen != set(selection):
                        raise PreviewError(
                            "Member details ended before the full selection"
                        )
                    self.source_details.update(seen)
                    break
                # Ordinary source expansion is atomic and does not accept a
                # page selector. It must never silently imply partial success.
                raise PreviewError(
                    "Source expansion unexpectedly returned a continuation"
                )

    def overview(self, revision):
        with self.lock:
            snapshot, result = self._load(revision)
            organization = snapshot.candidate
            value = {
                "work_ref": snapshot.work_ref,
                "result_ref": snapshot.result_ref,
                "revision": revision,
                "state": snapshot.state,
                "organization_kind": organization["kind"] if organization else "none",
                "logical_root": organization["logical_root"]
                if organization
                else "整理讨论",
                "scope_summary": _scope_summary(self.analysis)
                if self.analysis
                else None,
                "result": result,
                "working_notes": snapshot.working_notes,
                "preferences": snapshot.organization_preferences,
                "candidate_content_identity": snapshot.candidate_identity,
                "confirmation": None,
                "counts": {
                    key: len(organization.get(key, [])) if organization else 0
                    for key in ("groups", "other_outcomes", "decision_notes")
                },
            }
            if snapshot.state == "closed":
                value["confirmation"] = self.tool._publisher.read_verified(
                    Path(snapshot.published_path)
                )["seal"]["final_confirmation"]
            self._check(revision)
            return value

    def page(self, revision, collection, cursor=None):
        if (
            not isinstance(collection, str)
            or re.fullmatch(
                r"groups|other_outcomes|decision_notes|unassigned|(?:group|outcome|note):[0-9]+",
                collection,
            )
            is None
        ):
            raise PlanFailure("invalid_request", "Unknown collection")
        with self.lock:
            snapshot, _ = self._load(revision)
            organization = snapshot.candidate or {}
            limit, offset = 50, 0
            if cursor:
                offset, limit = _decode_cursor(
                    cursor,
                    work_ref=self.work_ref,
                    revision=revision,
                    collection=collection,
                    requested_limit=limit,
                    signing_key=self.tool._cursor_signing_key,
                )
            if collection.startswith("note:") and collection not in self.members:
                index = int(collection.split(":")[1])
                notes = organization.get("decision_notes", [])
                if not 0 <= index < len(notes):
                    raise PlanFailure("invalid_request", "Unknown note")
                self.members[collection] = self._sort(
                    self.resolver.resolve(notes[index]["applies_to"])
                )
            if collection in self.members:
                refs = self.members[collection]
                self._member_details(snapshot.result_ref, refs[offset : offset + limit])
                items = []
                for ref in refs[offset : offset + limit]:
                    view = self.resolver.source_views[ref]
                    path = view.get("locator", {}).get("value", ref)
                    item = {
                        "source_item_ref": ref,
                        "path": path,
                        "name": Path(path).name,
                        "qualifications": view.get("qualifications", []),
                        "observations": view.get("observations", []),
                    }
                    if collection.startswith("group:"):
                        group = organization["groups"][int(collection.split(":")[1])]
                        overrides = {
                            i["source_item_ref"]: i["name"]
                            for i in group["source_naming"].get("overrides", [])
                        }
                        item["target_name"] = overrides.get(ref, item["name"])
                    items.append(item)
                total = len(refs)
            elif collection in {"groups", "other_outcomes", "decision_notes"}:
                values = organization.get(collection, [])
                total = len(values)
                items = []
                for index in range(offset, min(offset + limit, total)):
                    item = dict(values[index])
                    prefix = {
                        "groups": "group",
                        "other_outcomes": "outcome",
                        "decision_notes": "note",
                    }[collection]
                    target = f"{prefix}:{index}"
                    if prefix == "note" and target not in self.members:
                        self.members[target] = self._sort(
                            self.resolver.resolve(item["applies_to"])
                        )
                    item.update(collection=target, total=len(self.members[target]))
                    if prefix == "group":
                        path = tuple(item["relative_path"])
                        # Full-snapshot totals include groups on later pages.
                        # They never depend on how many children the browser loaded.
                        item["path_totals"] = [
                            self.directory_totals[path[:depth]]
                            for depth in range(len(path) + 1)
                        ]
                        samples = self.renderer._samples(
                            self.analysis.group_representatives[index],
                            self.analysis,
                            frozenset(self.analysis.group_members[index]),
                            {},
                        )
                        item["samples"] = [
                            {
                                "label": s.label,
                                "source_item_ref": s.source_item_ref,
                                "evidence_ref": s.evidence_ref,
                                "available": s.uri is not None,
                            }
                            for s in samples
                        ]
                    items.append(item)
            elif collection == "unassigned" and not organization:
                items, total = [], 0
            else:
                raise PlanFailure("invalid_request", "Unknown collection")
            next_offset = offset + len(items)
            self._check(revision)
            return {
                "work_ref": self.work_ref,
                "revision": revision,
                "collection": collection,
                "items": items,
                "total": total,
                "complete": next_offset >= total,
                "next_cursor": None
                if next_offset >= total
                else _encode_cursor(
                    self.work_ref,
                    revision,
                    collection,
                    next_offset,
                    limit,
                    self.tool._cursor_signing_key,
                ),
            }

    def evidence(self, revision, ref):
        with self.lock:
            snapshot, _ = self._load(revision)
            response = self.renderer._read(
                {
                    "action": "review",
                    "result_ref": snapshot.result_ref,
                    "evidence_refs": [ref],
                    "page": {"limit": 1},
                }
            )
            if len(response["items"]) != 1:
                raise PreviewError("Evidence is unavailable")
            value = response["items"][0]
            self._check(revision)
            return value

    def asset(self, revision, ref):
        value = self.evidence(revision, ref)
        uri = _default_asset_resolver(ref, value)
        if uri is None:
            raise PreviewError(
                "Prepared image is missing, unreadable or has no supported local image access"
            )
        path = Path(unquote(urlparse(uri).path))
        # Only a prepared artifact in this explicit Dataset is served; prose and
        # browser-supplied paths never grant file custody. Resolve symlinks first.
        if not path.resolve().is_relative_to(self.tool.plan_store.parent.resolve()):
            raise PreviewError("Evidence image is outside the bound Dataset workspace")
        if path.stat().st_size > 16 * 1024 * 1024:
            raise PreviewError("Prepared image exceeds the 16 MiB delivery budget")
        data = path.read_bytes()
        self._check(revision)
        return data, path.suffix.lower()
