"""Read-only adapter for exact immutable PreCheck Results."""

from __future__ import annotations

from contextlib import contextmanager
import base64
import hmac
import hashlib
import json
from pathlib import Path
import sqlite3
from typing import Iterator, Protocol, cast
from urllib.parse import quote

from ._working_schema import SCHEMA_VERSION


class PrecheckReadBoundary(Protocol):
    """Process-local port for the public ``mediasense.precheck.read`` Tool."""

    name: str

    def read(self, request: dict[str, object]) -> dict[str, object]: ...


def require_precheck_read_boundary(value: object) -> PrecheckReadBoundary:
    """Reject incompatible local wiring before any stage operation starts."""

    if getattr(value, "name", None) != "mediasense.precheck.read" or not callable(
        getattr(value, "read", None)
    ):
        raise TypeError(
            "precheck_read must expose mediasense.precheck.read through read(request)"
        )
    return cast(PrecheckReadBoundary, value)


class PrecheckReadTool:
    """Implement ``mediasense.precheck.read`` inspect and traverse actions."""

    name = "mediasense.precheck.read"

    def __init__(self, database_path: Path) -> None:
        self.database_path = Path(database_path)
        self.workspace = self.database_path.parent.absolute()
        self._verify_schema()

    def read(self, request: dict[str, object]) -> dict[str, object]:
        result_ref = request.get("result_ref")
        if not isinstance(result_ref, str) or not result_ref:
            raise ValueError("result_ref must be a non-empty string")
        action = request.get("action")
        if action not in {"inspect", "traverse"}:
            raise ValueError("action must be inspect or traverse")
        allowed = {
            "result_ref",
            "action",
            "target",
            "relation",
            "direction",
            "filter",
            "page",
        }
        if unknown := set(request) - allowed:
            raise ValueError(f"unknown request fields: {sorted(unknown)}")

        loaded = self._load(result_ref)
        if isinstance(loaded, dict) and loaded.get("outcome") == "error":
            return loaded
        package, result_digest = loaded
        if action == "inspect":
            if any(
                key in request for key in ("relation", "direction", "filter", "page")
            ):
                raise ValueError("inspect does not accept traversal fields")
            return self._inspect(package, result_ref, request.get("target"))
        return self._traverse(package, result_ref, result_digest, request)

    def _load(self, result_ref: str) -> dict[str, object]:
        with self._connect() as connection:
            row = connection.execute(
                "SELECT * FROM sealed_results WHERE result_ref = ?", (result_ref,)
            ).fetchone()
            artifact_rows = (
                ()
                if row is None
                else tuple(
                    item
                    for item in connection.execute(
                        """
                    SELECT artifacts.* FROM result_artifacts
                    JOIN artifacts USING (artifact_id)
                    WHERE result_ref = ? ORDER BY artifact_id
                    """,
                        (result_ref,),
                    )
                )
            )
        if row is None:
            return _error(result_ref, "result_not_found", "Result does not exist")
        path = self.workspace / str(row["relative_path"])
        try:
            encoded = path.read_bytes()
        except OSError:
            return _error(
                result_ref,
                "result_not_available",
                "sealed Result bytes are unavailable",
            )
        if (
            len(encoded) != int(row["size_bytes"])
            or hashlib.sha256(encoded).hexdigest() != row["digest"]
        ):
            return _error(
                result_ref,
                "result_untrusted",
                "sealed Result integrity verification failed",
            )
        try:
            package = json.loads(encoded)
        except (UnicodeDecodeError, json.JSONDecodeError):
            return _error(
                result_ref,
                "result_untrusted",
                "sealed Result cannot be decoded",
            )
        if package.get("result", {}).get("ref") != result_ref:
            return _error(
                result_ref,
                "result_untrusted",
                "sealed Result identity does not match its reference",
            )
        for artifact in artifact_rows:
            artifact_path = self.workspace / str(artifact["relative_path"])
            try:
                artifact_bytes = artifact_path.read_bytes()
            except OSError:
                return _error(
                    result_ref,
                    "result_untrusted",
                    f"retained Artifact is unavailable: {artifact['artifact_id']}",
                )
            if (
                len(artifact_bytes) != int(artifact["size_bytes"])
                or hashlib.sha256(artifact_bytes).hexdigest() != artifact["digest"]
            ):
                return _error(
                    result_ref,
                    "result_untrusted",
                    f"retained Artifact is corrupt: {artifact['artifact_id']}",
                )
        return package, str(row["digest"])

    def _inspect(
        self,
        package: dict[str, object],
        result_ref: str,
        target: object,
    ) -> dict[str, object]:
        if target is None:
            view = package["result"]
        else:
            if (
                not isinstance(target, dict)
                or set(target) != {"kind", "ref"}
                or target.get("kind") not in {"dataset", "source_item", "evidence"}
                or not isinstance(target.get("ref"), str)
            ):
                raise ValueError(
                    "inspect target must be a typed Result-local reference"
                )
            kind = str(target["kind"])
            ref = str(target["ref"])
            if kind == "dataset":
                view = package["dataset"] if package["dataset"]["ref"] == ref else None
            else:
                collection = (
                    package["sources"] if kind == "source_item" else package["evidence"]
                )
                match = next(
                    (item for item in collection if item["view"]["ref"] == ref), None
                )
                view = None if match is None else match["view"]
            if view is None:
                return _error(result_ref, "target_not_found", "target is not in Result")
        return {
            "outcome": "ok",
            "result_ref": result_ref,
            "action": "inspect",
            "target": view,
        }

    def _traverse(
        self,
        package: dict[str, object],
        result_ref: str,
        result_digest: str,
        request: dict[str, object],
    ) -> dict[str, object]:
        relation = request.get("relation")
        direction = request.get("direction")
        target = request.get("target")
        valid = {
            ("accounts_for", "outbound"),
            ("entry_evidence", "outbound"),
            ("represents", "outbound"),
            ("represents", "inbound"),
            ("derived_from", "outbound"),
            ("expands_to", "outbound"),
        }
        if (relation, direction) not in valid:
            return _error(
                result_ref,
                "relation_not_applicable",
                "relationship direction is not supported",
            )
        if relation in {"accounts_for", "entry_evidence"}:
            if target is not None:
                raise ValueError(f"{relation} starts from the Result")
            origin = result_ref
        else:
            if not isinstance(target, str) or not target:
                raise ValueError("this traversal requires an opaque target reference")
            origin = target

        relationships = package["relationships"]
        if relation == "represents" and direction == "inbound":
            matches = [
                _reverse_member(item)
                for item in relationships
                if item["relation"] == relation and item["member"]["target"] == origin
            ]
        else:
            matches = [
                dict(item["member"])
                for item in relationships
                if item["relation"] == relation and item["origin"] == origin
            ]
        if relation not in {"accounts_for", "entry_evidence"} and not _has_origin(
            package, relation, direction, origin
        ):
            return _error(result_ref, "target_not_found", "origin is not in Result")

        filter_value = request.get("filter")
        derived_view = None
        if filter_value is not None:
            if filter_value != {"attention_only": True} or relation != "accounts_for":
                return _error(result_ref, "invalid_filter", "filter is not applicable")
            matches = [
                item
                for item in matches
                if item.get("condition") != "usable" or item.get("qualifications")
            ]
            derived_view = "attention_items"
        filter_key = "attention_items" if derived_view is not None else "none"

        page_request = request.get("page") or {}
        if not isinstance(page_request, dict) or set(page_request) - {
            "limit",
            "cursor",
        }:
            raise ValueError("page must contain only limit and cursor")
        limit = page_request.get("limit", 100)
        if (
            not isinstance(limit, int)
            or isinstance(limit, bool)
            or not 1 <= limit <= 1000
        ):
            raise ValueError("page limit must be an integer from 1 through 1000")
        offset = 0
        if cursor := page_request.get("cursor"):
            if not isinstance(cursor, str):
                raise ValueError("cursor must be a string")
            offset = _decode_cursor(
                cursor,
                result_digest,
                result_ref=result_ref,
                origin=origin,
                relation=str(relation),
                direction=str(direction),
                filter_key=filter_key,
            )
            if offset is None:
                return _error(result_ref, "invalid_cursor", "cursor is not valid here")
        selected = matches[offset : offset + limit]
        next_offset = offset + len(selected)
        page: dict[str, object] = {
            "returned": len(selected),
            "total": len(matches),
            "complete": next_offset >= len(matches),
        }
        if not page["complete"]:
            page["next_cursor"] = _encode_cursor(
                result_digest,
                result_ref=result_ref,
                origin=origin,
                relation=str(relation),
                direction=str(direction),
                filter_key=filter_key,
                offset=next_offset,
            )
        response: dict[str, object] = {
            "outcome": "ok",
            "result_ref": result_ref,
            "action": "traverse",
            "origin": origin,
            "relation": relation,
            "direction": direction,
            "items": selected,
            "page": page,
        }
        if derived_view is not None:
            response["derived_view"] = derived_view
        return response

    def _verify_schema(self) -> None:
        with self._connect() as connection:
            try:
                row = connection.execute(
                    "SELECT version FROM internal_schema WHERE singleton = 1"
                ).fetchone()
            except sqlite3.OperationalError as error:
                raise RuntimeError(
                    "initialize the PreCheck working store before PrecheckReadTool"
                ) from error
        if row is None or int(row["version"]) != SCHEMA_VERSION:
            raise RuntimeError("unsupported or uninitialized internal schema")

    @contextmanager
    def _connect(self) -> Iterator[sqlite3.Connection]:
        uri = f"file:{quote(str(self.database_path.absolute()))}?mode=ro"
        connection = sqlite3.connect(uri, uri=True, timeout=30)
        connection.row_factory = sqlite3.Row
        try:
            yield connection
        finally:
            connection.close()


def _has_origin(
    package: dict[str, object],
    relation: object,
    direction: object,
    origin: str,
) -> bool:
    sources = {item["view"]["ref"] for item in package["sources"]}
    evidence = {item["view"]["ref"] for item in package["evidence"]}
    if relation == "represents" and direction == "inbound":
        return origin in sources
    return origin in evidence


def _reverse_member(relationship: dict[str, object]) -> dict[str, object]:
    member: dict[str, object] = {"target": relationship["origin"]}
    for field in ("basis", "qualifications"):
        if field in relationship["member"]:
            member[field] = relationship["member"][field]
    return member


def _encode_cursor(
    result_digest: str,
    *,
    result_ref: str,
    origin: str,
    relation: str,
    direction: str,
    filter_key: str,
    offset: int,
) -> str:
    payload = json.dumps(
        {
            "direction": direction,
            "filter": filter_key,
            "offset": offset,
            "origin": origin,
            "relation": relation,
            "result_ref": result_ref,
        },
        separators=(",", ":"),
        sort_keys=True,
    ).encode("utf-8")
    signature = hmac.new(
        result_digest.encode("ascii"), payload, hashlib.sha256
    ).digest()
    token = base64.urlsafe_b64encode(payload + signature).rstrip(b"=").decode("ascii")
    return f"cursor:{token}"


def _decode_cursor(
    cursor: str,
    result_digest: str,
    *,
    result_ref: str,
    origin: str,
    relation: str,
    direction: str,
    filter_key: str,
) -> int | None:
    if not cursor.startswith("cursor:"):
        return None
    token = cursor.removeprefix("cursor:")
    try:
        padding = "=" * (-len(token) % 4)
        decoded = base64.urlsafe_b64decode(token + padding)
        payload, signature = decoded[:-32], decoded[-32:]
        expected = hmac.new(
            result_digest.encode("ascii"), payload, hashlib.sha256
        ).digest()
        if not hmac.compare_digest(signature, expected):
            return None
        value = json.loads(payload)
    except (ValueError, UnicodeDecodeError, json.JSONDecodeError):
        return None
    if not isinstance(value, dict) or value != {
        "direction": direction,
        "filter": filter_key,
        "offset": value.get("offset"),
        "origin": origin,
        "relation": relation,
        "result_ref": result_ref,
    }:
        return None
    offset = value["offset"]
    if not isinstance(offset, int) or isinstance(offset, bool) or offset < 0:
        return None
    return offset


def _error(
    result_ref: str,
    code: str,
    message: str,
) -> dict[str, object]:
    return {
        "outcome": "error",
        "result_ref": result_ref,
        "error": {"code": code, "message": message},
    }


__all__ = ["PrecheckReadTool"]
