"""Factual source-tree projection and exact scope-selection helpers."""

from __future__ import annotations

from collections.abc import Iterable, Mapping
from dataclasses import dataclass, field
import hashlib
import json
from pathlib import PurePosixPath


_DEFAULT_MAX_ENTRIES = 63
_REPRESENTATIVE_LIMIT = 3
_EXCEPTION_LIMIT = 256


class ScopeSelectionError(ValueError):
    """A requested source-scope selection is ambiguous or out of date."""


@dataclass(slots=True)
class _ScopeEntry:
    path: str
    node_type: str = "directory"
    file_count: int = 0
    byte_count: int = 0
    unknown_size_count: int = 0
    kind_counts: dict[str, int] = field(default_factory=dict)
    size_buckets: dict[str, int] = field(default_factory=dict)
    representative_paths: list[str] = field(default_factory=list)
    immediate_child_count: int = 0

    def observe(self, fact: Mapping[str, object]) -> None:
        self.file_count += 1
        kind = str(fact["kind"])
        self.kind_counts[kind] = self.kind_counts.get(kind, 0) + 1
        size = fact.get("size_bytes")
        bucket = _size_bucket(size)
        self.size_buckets[bucket] = self.size_buckets.get(bucket, 0) + 1
        if isinstance(size, int):
            self.byte_count += size
        else:
            self.unknown_size_count += 1
        if len(self.representative_paths) < _REPRESENTATIVE_LIMIT:
            self.representative_paths.append(str(fact["relative_path"]))


def build_scope_inventory(
    facts: Iterable[Mapping[str, object]],
    issues: Iterable[Mapping[str, object]],
    *,
    scan_generation: int,
    scope_path: str = ".",
    scope_after: str | None = None,
    cursor_ref: str = "",
    max_entries: int = _DEFAULT_MAX_ENTRIES,
) -> dict[str, object]:
    """Build immediate entries while hashing the complete factual inventory."""

    if max_entries < 1:
        raise ValueError("scope bounds must allow at least one entry")
    root_path = normalize_scope_path(scope_path, allow_root=True)
    root_parts = () if root_path == "." else PurePosixPath(root_path).parts
    # Decode only to obtain a candidate offset; the complete inventory below
    # authenticates it before any data is returned.
    after_path = None
    if scope_after is not None:
        import base64

        try:
            payload = json.loads(
                base64.urlsafe_b64decode(scope_after.removeprefix("scope-cursor:"))
            )
            after_path = normalize_scope_path(payload["after"], allow_root=False)
        except (ValueError, KeyError, TypeError) as error:
            raise ScopeSelectionError("invalid scope cursor") from error
    nodes: dict[str, _ScopeEntry] = {}
    child_dirs: dict[str, str] = {}
    digest = hashlib.sha256()
    selected_seen = False
    has_more = False
    for fact in facts:
        digest.update((_json(_canonical_fact(fact)) + "\n").encode())
        parts = PurePosixPath(str(fact["relative_path"])).parts
        if not _is_at_or_below(parts, root_parts):
            continue
        selected_seen = True
        suffix = parts[len(root_parts) :]
        child_path = PurePosixPath(*root_parts, *suffix[:1]).as_posix()
        if after_path is not None and child_path <= after_path:
            continue
        node = nodes.get(child_path)
        if node is None:
            if len(nodes) >= min(63, max_entries):
                has_more = True
                continue
            node = _ScopeEntry(
                path=child_path, node_type="file" if len(suffix) <= 1 else "directory"
            )
            nodes[child_path] = node
        node.observe(fact)
        if len(suffix) > 2 and child_dirs.get(child_path) != suffix[1]:
            node.immediate_child_count += 1
            child_dirs[child_path] = suffix[1]
    issue_values = []
    issue_count = 0
    for issue in issues:
        issue_count += 1
        canonical = {
            "relative_path": str(issue["relative_path"]),
            "code": str(issue["code"]),
            "blocked": bool(issue["blocked"]),
            "basis": list(issue.get("basis", ())),
        }
        digest.update((_json({"issue": canonical}) + "\n").encode())
        if len(issue_values) < 3:
            issue_values.append(
                {
                    "path": canonical["relative_path"],
                    "code": canonical["code"],
                    "message": "; ".join(map(str, canonical["basis"]))
                    or canonical["code"],
                }
            )
    if root_path != "." and not selected_seen:
        raise ScopeSelectionError("scope_path does not identify an inventory node")
    fingerprint = "sha256:" + digest.hexdigest()
    if scope_after is not None and payload != {
        "fingerprint": fingerprint,
        "root": root_path,
        "after": after_path,
        "run": cursor_ref,
    }:
        raise ScopeSelectionError("scope cursor is stale or belongs to another view")
    entries = []
    for node in nodes.values():
        entries.append(_entry_value(node))
    next_after = None
    if has_more and entries:
        import base64

        next_after = (
            "scope-cursor:"
            + base64.urlsafe_b64encode(
                _json(
                    {
                        "fingerprint": fingerprint,
                        "root": root_path,
                        "after": entries[-1]["path"],
                        "run": cursor_ref,
                    }
                ).encode()
            ).decode()
        )
    result = {
        "inventory_fingerprint": fingerprint,
        "scan_generation": scan_generation,
        "complete": issue_count == 0,
        "view": {"root": root_path, "entries": entries, "next_after": next_after},
    }
    if issue_values:
        result["issues"] = issue_values
    if issue_count > len(issue_values):
        result["issues_truncated"] = True
    return result


def inventory_fingerprint(
    facts: Iterable[Mapping[str, object]],
    issues: Iterable[Mapping[str, object]],
) -> str:
    """Return the complete inventory identity without constructing a tree view."""

    digest = hashlib.sha256()
    for fact in facts:
        digest.update(_json(_canonical_fact(fact)).encode("utf-8"))
        digest.update(b"\n")
    for issue in issues:
        digest.update(
            _json(
                {
                    "issue": {
                        "relative_path": str(issue["relative_path"]),
                        "code": str(issue["code"]),
                        "blocked": bool(issue["blocked"]),
                        "basis": list(issue.get("basis", ())),
                    }
                }
            ).encode("utf-8")
        )
        digest.update(b"\n")
    return "sha256:" + digest.hexdigest()


def normalize_scope_path(value: object, *, allow_root: bool = False) -> str:
    if not isinstance(value, str) or not value:
        raise ScopeSelectionError("scope path must be a non-empty string")
    path = PurePosixPath(value)
    if path.is_absolute() or ".." in path.parts:
        raise ScopeSelectionError("scope path must remain source-relative")
    normalized = path.as_posix()
    if normalized in {"", "."}:
        if allow_root:
            return "."
        raise ScopeSelectionError("the source root cannot be an exception")
    if normalized.startswith("./"):
        normalized = normalized[2:]
    return normalized


def validate_scope_selection(
    decision: object,
    *,
    inventory_fingerprint_value: str,
    existing_paths: Iterable[str],
) -> dict[str, object]:
    if not isinstance(decision, dict):
        raise ScopeSelectionError("source-scope decision must be an object")
    if set(decision) != {
        "kind",
        "inventory_fingerprint",
        "default_disposition",
        "exceptions",
    }:
        raise ScopeSelectionError("source-scope decision has unknown or missing fields")
    if decision["kind"] != "source_scope":
        raise ScopeSelectionError("source-scope decision kind must be source_scope")
    if decision["inventory_fingerprint"] != inventory_fingerprint_value:
        raise ScopeSelectionError("source-scope decision names a stale inventory")
    default = decision["default_disposition"]
    if default not in {"include", "exclude"}:
        raise ScopeSelectionError("default_disposition must be include or exclude")
    raw_exceptions = decision["exceptions"]
    if not isinstance(raw_exceptions, list):
        raise ScopeSelectionError("exceptions must be an array")
    if len(raw_exceptions) > _EXCEPTION_LIMIT:
        raise ScopeSelectionError("scope selection has too many exceptions")
    exceptions = tuple(
        normalize_scope_path(value, allow_root=False) for value in raw_exceptions
    )
    if len(set(exceptions)) != len(exceptions):
        raise ScopeSelectionError("scope exceptions must be unique")
    ordered = tuple(sorted(exceptions))
    for index, path in enumerate(ordered):
        prefix = path + "/"
        if any(other.startswith(prefix) for other in ordered[index + 1 :]):
            raise ScopeSelectionError("scope exceptions must not overlap")
    missing = set(ordered)
    for item in existing_paths:
        for path in tuple(missing):
            if item == path or item.startswith(path + "/"):
                missing.remove(path)
        if not missing:
            break
    if missing:
        raise ScopeSelectionError(
            "scope exception is absent from inventory: " + sorted(missing)[0]
        )
    return {
        "kind": "source_scope",
        "inventory_fingerprint": inventory_fingerprint_value,
        "default_disposition": default,
        "exceptions": list(ordered),
    }


def selection_digest(selection: Mapping[str, object]) -> str:
    return "sha256:" + hashlib.sha256(_json(selection).encode("utf-8")).hexdigest()


def _canonical_fact(fact: Mapping[str, object]) -> dict[str, object]:
    return {
        key: fact.get(key)
        for key in (
            "relative_path",
            "kind",
            "scope",
            "condition",
            "basis",
            "size_bytes",
            "mtime_ns",
            "device_id",
            "inode",
            "mode",
            "fingerprint_algorithm",
            "fingerprint",
            "producer_identity",
            "reuse_domain",
        )
    }


def _entry_value(node: _ScopeEntry) -> dict[str, object]:
    return {
        "path": node.path,
        "node_type": node.node_type,
        "file_count": node.file_count,
        "byte_count": node.byte_count,
        "unknown_size_count": node.unknown_size_count,
        "kind_counts": [
            {"kind": key, "count": node.kind_counts[key]}
            for key in sorted(node.kind_counts)
        ],
        "size_buckets": [
            {"bucket": key, "count": node.size_buckets[key]}
            for key in (
                "unknown",
                "zero",
                "under_1_mib",
                "1_to_10_mib",
                "10_to_100_mib",
                "100_mib_or_more",
            )
            if key in node.size_buckets
        ],
        "representative_paths": list(node.representative_paths),
        "child_count": node.immediate_child_count,
    }


def _size_bucket(value: object) -> str:
    if not isinstance(value, int):
        return "unknown"
    if value == 0:
        return "zero"
    if value < 1024 * 1024:
        return "under_1_mib"
    if value < 10 * 1024 * 1024:
        return "1_to_10_mib"
    if value < 100 * 1024 * 1024:
        return "10_to_100_mib"
    return "100_mib_or_more"


def _is_at_or_below(parts: tuple[str, ...], root: tuple[str, ...]) -> bool:
    return len(parts) >= len(root) and parts[: len(root)] == root


def _json(value: object) -> str:
    return json.dumps(
        value,
        ensure_ascii=False,
        allow_nan=False,
        separators=(",", ":"),
        sort_keys=True,
    )


__all__ = [
    "ScopeSelectionError",
    "build_scope_inventory",
    "inventory_fingerprint",
    "normalize_scope_path",
    "selection_digest",
    "validate_scope_selection",
]
