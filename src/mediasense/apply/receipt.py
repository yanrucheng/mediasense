"""Immutable Apply Receipt construction, publication, and bounded reading."""

from __future__ import annotations

import base64
import binascii
from collections.abc import Iterator
from dataclasses import dataclass
import hashlib
import json
import os
from pathlib import Path
import re
from typing import Mapping

from jsonschema import Draft202012Validator, ValidationError


class ReceiptError(RuntimeError):
    """A Receipt could not be validated, published, or read safely."""

    def __init__(self, message: str, *, code: str = "receipt_untrusted") -> None:
        self.code = code
        super().__init__(message)


@dataclass(frozen=True, slots=True)
class ReceiptPackage:
    """One logical Receipt plus optional immutable operation segments."""

    document: dict[str, object]
    operation_index: dict[str, object] | None = None
    operation_segments: tuple[dict[str, object], ...] = ()


def canonical_bytes(value: object) -> bytes:
    return json.dumps(
        value, ensure_ascii=False, separators=(",", ":"), sort_keys=True
    ).encode("utf-8")


def content_identity(value: object) -> str:
    return "sha256:" + hashlib.sha256(canonical_bytes(value)).hexdigest()


class ReceiptStore:
    """Authoritative home for immutable Receipt packages."""

    def __init__(self, root: Path, schema_path: Path) -> None:
        self.root = Path(root)
        self.schema_path = Path(schema_path)
        schema = json.loads(self.schema_path.read_text(encoding="utf-8"))
        Draft202012Validator.check_schema(schema)
        self._validator = Draft202012Validator(schema)

    def prepare(
        self,
        receipt: Mapping[str, object],
        *,
        operations: list[dict[str, object]] | None = None,
    ) -> ReceiptPackage:
        """Choose an inline or segmented physical representation before publication."""

        document = json.loads(json.dumps(receipt, ensure_ascii=False))
        sealed = document.get("sealed_content")
        seal = document.get("seal")
        if not isinstance(sealed, dict) or not isinstance(seal, dict):
            raise ReceiptError("Receipt has no valid sealed content")
        ledger = sealed.get("operation_ledger")
        if not isinstance(ledger, dict):
            raise ReceiptError("Receipt has no valid operation ledger")
        if ledger.get("kind") == "inline":
            values = ledger.get("items")
            if not isinstance(values, list):
                raise ReceiptError("inline Receipt ledger has no item list")
            operation_values = [dict(item) for item in values]
            if len(operation_values) <= _OPERATION_SEGMENT_SIZE:
                self._validator.validate(document)
                return ReceiptPackage(document=document)
        elif ledger.get("kind") == "immutable_segments":
            if operations is None:
                raise ReceiptError(
                    "segmented Receipt recovery requires durable operation facts"
                )
            operation_values = [dict(item) for item in operations]
        else:
            self._validator.validate(document)
            return ReceiptPackage(document=document)

        segments = tuple(
            {
                "kind": "mediasense.apply-receipt-operation-segment-v1",
                "index": index,
                "items": operation_values[start : start + _OPERATION_SEGMENT_SIZE],
            }
            for index, start in enumerate(
                range(0, len(operation_values), _OPERATION_SEGMENT_SIZE)
            )
        )
        index_document: dict[str, object] = {
            "kind": "mediasense.apply-receipt-operation-index-v1",
            "item_count": len(operation_values),
            "segments": [
                {
                    "index": segment["index"],
                    "item_count": len(segment["items"]),
                    "content_identity": content_identity(segment),
                }
                for segment in segments
            ],
        }
        manifest = {
            "kind": "immutable_segments",
            "coverage": "all_materialization_operations",
            "item_count": len(operation_values),
            "segment_count": len(segments),
            "content_identity": content_identity(index_document),
        }
        if ledger.get("kind") == "immutable_segments" and ledger != manifest:
            raise ReceiptError(
                "durable operations do not match Receipt segment manifest"
            )
        sealed["operation_ledger"] = manifest
        seal["content_identity"] = content_identity(sealed)
        self._validator.validate(document)
        return ReceiptPackage(
            document=document,
            operation_index=index_document,
            operation_segments=segments,
        )

    def publish(self, receipt: ReceiptPackage | Mapping[str, object]) -> Path:
        """Validate and publish one Receipt without replacing prior history."""

        package = (
            receipt if isinstance(receipt, ReceiptPackage) else self.prepare(receipt)
        )
        document = package.document
        self._validator.validate(document)
        sealed = document["sealed_content"]
        seal = document["seal"]
        assert isinstance(sealed, dict) and isinstance(seal, dict)
        observed = content_identity(sealed)
        if seal.get("content_identity") != observed:
            raise ReceiptError("Receipt content identity does not match sealed content")
        receipt_ref = str(sealed["receipt_ref"])
        artifact = self.artifact_path(receipt_ref)
        try:
            self.root.mkdir(parents=True, exist_ok=True)
        except OSError as error:
            raise ReceiptError(
                f"Receipt root cannot be prepared: {self.root}"
            ) from error
        if self.root.is_symlink() or not self.root.is_dir():
            raise ReceiptError("Receipt root is not a safe directory")
        try:
            artifact.mkdir()
        except FileExistsError:
            if artifact.is_symlink() or not artifact.is_dir():
                raise ReceiptError("Receipt artifact path is unsafe")
        except OSError as error:
            raise ReceiptError(
                f"Receipt artifact directory cannot be created: {artifact}"
            ) from error
        final = artifact / "receipt.json"
        encoded = canonical_bytes(document) + b"\n"
        try:
            if package.operation_index is not None:
                for segment in package.operation_segments:
                    index = int(segment["index"])
                    _publish_immutable_file(
                        artifact / _segment_name(index),
                        canonical_bytes(segment) + b"\n",
                    )
                _publish_immutable_file(
                    artifact / _OPERATION_INDEX,
                    canonical_bytes(package.operation_index) + b"\n",
                )
            _publish_immutable_file(final, encoded)
            _fsync_directory(artifact)
        except ReceiptError:
            raise
        except OSError as error:
            raise ReceiptError("Receipt package publication failed") from error
        return final

    def read(self, receipt_ref: str) -> dict[str, object]:
        path = self.artifact_path(receipt_ref) / "receipt.json"
        try:
            document = json.loads(path.read_text(encoding="utf-8"))
        except FileNotFoundError as error:
            raise ReceiptError(
                f"Receipt does not exist: {receipt_ref}", code="receipt_not_found"
            ) from error
        except OSError as error:
            raise ReceiptError(
                f"Receipt is unavailable: {receipt_ref}", code="receipt_unavailable"
            ) from error
        except json.JSONDecodeError as error:
            raise ReceiptError(
                f"Receipt is invalid: {receipt_ref}", code="receipt_untrusted"
            ) from error
        try:
            self._validator.validate(document)
        except ValidationError as error:
            raise ReceiptError(
                "Receipt does not conform to its schema", code="receipt_untrusted"
            ) from error
        if document["sealed_content"]["receipt_ref"] != receipt_ref:
            raise ReceiptError(
                "Receipt reference does not match its identity",
                code="receipt_untrusted",
            )
        if document["seal"]["content_identity"] != content_identity(
            document["sealed_content"]
        ):
            raise ReceiptError(
                "Receipt integrity verification failed", code="receipt_untrusted"
            )
        ledger = document["sealed_content"]["operation_ledger"]
        if ledger["kind"] == "immutable_segments":
            observed_count = sum(
                1 for _item in self._iter_segment_items(path.parent, ledger)
            )
            if observed_count != ledger["item_count"]:
                raise ReceiptError(
                    "Receipt operation segments have incomplete coverage"
                )
        return document

    def operation_items(
        self, receipt_ref: str, receipt: Mapping[str, object] | None = None
    ) -> list[dict[str, object]]:
        """Load and verify the complete logical ledger for whole-Run rewind."""

        document = dict(receipt or self.read(receipt_ref))
        ledger = document["sealed_content"]["operation_ledger"]
        if ledger["kind"] == "inline":
            return [dict(item) for item in ledger["items"]]
        artifact = self.artifact_path(receipt_ref)
        return list(self._iter_segment_items(artifact, ledger))

    def operation_page(
        self,
        *,
        receipt_ref: str,
        receipt: Mapping[str, object],
        section: str,
        offset: int,
        limit: int,
        filter_value: Mapping[str, object] | None,
    ) -> tuple[list[dict[str, object]], int]:
        """Read a bounded logical page while holding at most one segment in memory."""

        ledger = receipt["sealed_content"]["operation_ledger"]
        if ledger["kind"] == "inline":
            values = _operation_view_items(ledger["items"], section, filter_value)
            return values[offset : offset + limit], len(values)
        matched = 0
        selected: list[dict[str, object]] = []
        artifact = self.artifact_path(receipt_ref)
        for item in self._iter_segment_items(artifact, ledger):
            projected = _operation_view_item(item, section, filter_value)
            if projected is None:
                continue
            if offset <= matched < offset + limit:
                selected.append(projected)
            matched += 1
        return selected, matched

    def _operation_index(
        self, artifact: Path, ledger: Mapping[str, object]
    ) -> dict[str, object]:
        path = artifact / _OPERATION_INDEX
        if path.is_symlink() or not path.is_file():
            raise ReceiptError("Receipt operation index is unavailable or unsafe")
        try:
            index = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as error:
            raise ReceiptError("Receipt operation index is invalid") from error
        if not isinstance(index, dict) or content_identity(index) != ledger.get(
            "content_identity"
        ):
            raise ReceiptError("Receipt operation index integrity verification failed")
        entries = index.get("segments")
        if (
            index.get("kind") != "mediasense.apply-receipt-operation-index-v1"
            or index.get("item_count") != ledger.get("item_count")
            or not isinstance(entries, list)
            or len(entries) != ledger.get("segment_count")
        ):
            raise ReceiptError("Receipt operation index does not match its manifest")
        for expected, entry in enumerate(entries):
            if (
                not isinstance(entry, dict)
                or entry.get("index") != expected
                or not isinstance(entry.get("item_count"), int)
                or entry["item_count"] < 1
                or not isinstance(entry.get("content_identity"), str)
            ):
                raise ReceiptError("Receipt operation index has an invalid segment")
        if sum(int(entry["item_count"]) for entry in entries) != ledger.get(
            "item_count"
        ):
            raise ReceiptError("Receipt operation index has incomplete item coverage")
        return index

    def _iter_segment_items(
        self, artifact: Path, ledger: Mapping[str, object]
    ) -> Iterator[dict[str, object]]:
        index = self._operation_index(artifact, ledger)
        entries = index["segments"]
        assert isinstance(entries, list)
        for entry in entries:
            assert isinstance(entry, dict)
            segment_number = int(entry["index"])
            path = artifact / _segment_name(segment_number)
            if path.is_symlink() or not path.is_file():
                raise ReceiptError("Receipt operation segment is unavailable or unsafe")
            try:
                segment = json.loads(path.read_text(encoding="utf-8"))
            except (OSError, json.JSONDecodeError) as error:
                raise ReceiptError("Receipt operation segment is invalid") from error
            if (
                not isinstance(segment, dict)
                or segment.get("kind")
                != "mediasense.apply-receipt-operation-segment-v1"
                or segment.get("index") != segment_number
                or content_identity(segment) != entry["content_identity"]
            ):
                raise ReceiptError("Receipt operation segment integrity check failed")
            items = segment.get("items")
            if not isinstance(items, list) or len(items) != entry["item_count"]:
                raise ReceiptError("Receipt operation segment item count is invalid")
            for item in items:
                if not isinstance(item, dict):
                    raise ReceiptError(
                        "Receipt operation segment contains an invalid item"
                    )
                yield dict(item)

    def artifact_path(self, receipt_ref: str) -> Path:
        prefix = "apply-receipt:"
        if not receipt_ref.startswith(prefix):
            raise ReceiptError("invalid Receipt reference", code="invalid_request")
        token = receipt_ref.removeprefix(prefix)
        if not token or any(character not in _SAFE_TOKEN for character in token):
            raise ReceiptError("unsafe Receipt reference", code="invalid_request")
        return self.root / token


class ApplyReceiptReader:
    """Bounded immutable read projection over one Receipt store."""

    name = "mediasense.apply.read"

    def __init__(self, store: ReceiptStore, schema_path: Path | None = None) -> None:
        self.store = store
        path = schema_path or (
            Path(__file__).resolve().parents[3]
            / "docs"
            / "spec"
            / "spec-260829-0050-apply"
            / "apply-read.tool.json"
        )
        schema = json.loads(Path(path).read_text(encoding="utf-8"))
        self._input = Draft202012Validator(schema["inputSchema"])
        self._output = Draft202012Validator(schema["outputSchema"])

    def read(self, request: Mapping[str, object]) -> dict[str, object]:
        payload = dict(request)
        try:
            self._input.validate(payload)
            receipt_ref = str(payload["receipt_ref"])
            action = str(payload["action"])
            receipt = self.store.read(receipt_ref)
            if action == "inspect":
                return self._validated_response(
                    {
                        "outcome": "ok",
                        "action": "inspect",
                        "receipt_ref": receipt_ref,
                        "receipt": _receipt_summary(receipt),
                    }
                )
            section = str(payload["section"])
            page = payload.get("page") or {}
            assert isinstance(page, Mapping)
            limit = int(page.get("limit", 100))
            offset = 0
            filter_value = payload.get("filter")
            assert filter_value is None or isinstance(filter_value, Mapping)
            cursor = page.get("cursor")
            if cursor is not None:
                offset = _decode_cursor(str(cursor), receipt, section, filter_value)
            content = receipt["sealed_content"]
            assert isinstance(content, Mapping)
            ledger = content["operation_ledger"]
            if section in {"operations", "exceptions"} and isinstance(ledger, Mapping):
                selected, total = self.store.operation_page(
                    receipt_ref=receipt_ref,
                    receipt=receipt,
                    section=section,
                    offset=offset,
                    limit=limit,
                    filter_value=filter_value,
                )
            else:
                items = _section_items(receipt, section)
                if filter_value is not None:
                    items = _filter_items(items, filter_value)
                selected = items[offset : offset + limit]
                total = len(items)
            next_offset = offset + len(selected)
            complete = next_offset >= total
            page_result: dict[str, object] = {
                "returned": len(selected),
                "total": total,
                "complete": complete,
            }
            if not complete:
                page_result["next_cursor"] = _encode_cursor(
                    receipt, section, next_offset, filter_value
                )
            return self._validated_response(
                {
                    "outcome": "ok",
                    "action": "traverse",
                    "receipt_ref": receipt_ref,
                    "section": section,
                    "items": selected,
                    "page": page_result,
                }
            )
        except ValidationError:
            return self._error_response(
                payload,
                "invalid_request",
                "Apply Read request does not conform to its contract.",
            )
        except ReceiptError as error:
            message = {
                "invalid_cursor": "Receipt cursor is invalid or does not match this query.",
                "invalid_request": "Apply Read request is invalid.",
                "receipt_not_found": "Receipt does not exist.",
                "receipt_unavailable": "Receipt is unavailable.",
                "receipt_untrusted": "Receipt integrity verification failed.",
            }.get(error.code, "Receipt read failed.")
            return self._error_response(payload, error.code, message)

    def _error_response(
        self,
        request: Mapping[str, object],
        code: str,
        message: str,
    ) -> dict[str, object]:
        action = request.get("action")
        response: dict[str, object] = {
            "outcome": "error",
            "action": action if action in {"inspect", "traverse"} else "unknown",
            "error": {"code": code, "message": message},
        }
        receipt_ref = request.get("receipt_ref")
        if isinstance(receipt_ref, str) and _RECEIPT_REF.fullmatch(receipt_ref):
            response["receipt_ref"] = receipt_ref
        return self._validated_response(response)

    def _validated_response(self, response: dict[str, object]) -> dict[str, object]:
        self._output.validate(response)
        return response


def _receipt_summary(receipt: Mapping[str, object]) -> dict[str, object]:
    content = receipt["sealed_content"]
    assert isinstance(content, Mapping)
    binding = content["execution_binding"]
    assert isinstance(binding, Mapping)
    if binding["kind"] == "forward":
        destination = binding["destination"]
        assert isinstance(destination, Mapping)
        summary_binding: dict[str, object] = {
            "kind": "forward",
            "source_root_count": len(binding["source_roots"]),
            "destination_parent": destination["parent"],
            "resolved_logical_root": destination["resolved_logical_root"],
        }
    else:
        summary_binding = {
            "kind": "rewind",
            "rewind_of_receipt_ref": binding["rewind_of_receipt_ref"],
            "restored_source_parents": binding["restored_source_parents"],
        }
    preservation = content["metadata_preservation"]
    assert isinstance(preservation, Mapping)
    verification = content["verification"]
    assert isinstance(verification, Mapping)
    result: dict[str, object] = {
        "receipt_ref": content["receipt_ref"],
        "run_ref": content["run_ref"],
        "frozen_plan_ref": content["frozen_plan_ref"],
        "effect": content["effect"],
        "execution_binding": summary_binding,
        "completion": content["completion"],
        "closure": content["closure"],
        "accounting": content["accounting"],
        "verification": {
            "unplanned_targets": verification["unplanned_targets"],
            "unplanned_renames": verification["unplanned_renames"],
            "unverified_items": verification["unverified_items"],
        },
        "metadata_preservation": {
            "profile": preservation["profile"],
            "content_verification_result": preservation["content_verification"][
                "result"
            ],
            "unpreserved_attribute_count": len(preservation["unpreserved_attributes"]),
            "accepted_discrepancy_count": len(
                preservation["accepted_discrepancy_refs"]
            ),
        },
        "integrity": "valid",
    }
    rewind = content["recovery"].get("rewind_window_ends_at")
    if rewind is not None:
        result["rewind_window_ends_at"] = rewind
    return result


def _section_items(
    receipt: Mapping[str, object], section: str
) -> list[dict[str, object]]:
    content = receipt["sealed_content"]
    assert isinstance(content, Mapping)
    if section in {"operations", "exceptions"}:
        ledger = content["operation_ledger"]
        assert isinstance(ledger, Mapping)
        if ledger["kind"] != "inline":
            raise ReceiptError("segmented operations require the Receipt store")
        return _operation_view_items(ledger["items"], section, None)
    if section == "created_directories":
        return [
            {"path": item["path"], "rewind_rule": item["rewind_rule"]}
            for item in content["created_directories"]
        ]
    if section == "metadata_discrepancies":
        preservation = content["metadata_preservation"]
        accepted = set(preservation["accepted_discrepancy_refs"])
        authorization_by_ref = {
            ref: authorization["authorization_ref"]
            for authorization in preservation["discrepancy_authorizations"]
            for ref in authorization["accepted_discrepancy_refs"]
        }
        values = []
        for item in preservation["unpreserved_attributes"]:
            value = dict(item)
            value["accepted"] = item["discrepancy_ref"] in accepted
            if value["accepted"]:
                value["authorization_ref"] = authorization_by_ref[
                    item["discrepancy_ref"]
                ]
            values.append(value)
        return values
    raise ReceiptError(f"unsupported Receipt section: {section}")


def _filter_items(
    items: list[dict[str, object]], filter_value: Mapping[str, object]
) -> list[dict[str, object]]:
    result = items
    if "source_item_ref" in filter_value:
        result = [
            item
            for item in result
            if item.get("source_item_ref") == filter_value["source_item_ref"]
        ]
    if "result" in filter_value:
        result = [
            item for item in result if item.get("result") == filter_value["result"]
        ]
    return result


def _operation_view_items(
    items: object,
    section: str,
    filter_value: Mapping[str, object] | None,
) -> list[dict[str, object]]:
    if not isinstance(items, list):
        raise ReceiptError("Receipt operation ledger is invalid")
    result = []
    for item in items:
        if not isinstance(item, Mapping):
            raise ReceiptError("Receipt operation ledger contains an invalid item")
        projected = _operation_view_item(item, section, filter_value)
        if projected is not None:
            result.append(projected)
    return result


def _operation_view_item(
    item: Mapping[str, object],
    section: str,
    filter_value: Mapping[str, object] | None,
) -> dict[str, object] | None:
    if section == "exceptions" and item.get("result") == "completed_and_verified":
        return None
    if filter_value is not None:
        if (
            "source_item_ref" in filter_value
            and item.get("source_item_ref") != filter_value["source_item_ref"]
        ):
            return None
        if "result" in filter_value and item.get("result") != filter_value["result"]:
            return None
    result = dict(item)
    if isinstance(result.get("reason"), Mapping):
        reason = result["reason"]
        assert isinstance(reason, Mapping)
        result["reason"] = str(reason["message"])
    return result


def _encode_cursor(
    receipt: Mapping[str, object],
    section: str,
    offset: int,
    filter_value: Mapping[str, object] | None,
) -> str:
    identity = receipt["seal"]["content_identity"]
    payload = canonical_bytes(
        {
            "receipt_identity": identity,
            "section": section,
            "filter_identity": content_identity(dict(filter_value or {})),
            "offset": offset,
        }
    )
    signature = hashlib.sha256(payload).digest()
    return "opaque:" + base64.urlsafe_b64encode(payload + signature).decode("ascii")


def _decode_cursor(
    cursor: str,
    receipt: Mapping[str, object],
    section: str,
    filter_value: Mapping[str, object] | None,
) -> int:
    try:
        raw = base64.urlsafe_b64decode(cursor.removeprefix("opaque:"))
        payload, signature = raw[:-32], raw[-32:]
        if hashlib.sha256(payload).digest() != signature:
            raise ValueError
        value = json.loads(payload)
    except (
        ValueError,
        UnicodeDecodeError,
        json.JSONDecodeError,
        binascii.Error,
    ) as error:
        raise ReceiptError("invalid Receipt cursor", code="invalid_cursor") from error
    if (
        not cursor.startswith("opaque:")
        or value.get("receipt_identity") != receipt["seal"]["content_identity"]
        or value.get("section") != section
        or value.get("filter_identity") != content_identity(dict(filter_value or {}))
        or not isinstance(value.get("offset"), int)
        or value["offset"] < 0
    ):
        raise ReceiptError(
            "Receipt cursor does not bind this query", code="invalid_cursor"
        )
    return value["offset"]


def _fsync_directory(path: Path) -> None:
    descriptor = os.open(path, os.O_RDONLY)
    try:
        os.fsync(descriptor)
    finally:
        os.close(descriptor)


def _publish_immutable_file(path: Path, encoded: bytes) -> None:
    if os.path.lexists(path):
        if path.is_symlink() or not path.is_file():
            raise ReceiptError("Receipt package path is not a regular file")
        if path.read_bytes() != encoded:
            raise ReceiptError("existing Receipt artifact has conflicting content")
        return
    temporary = path.parent / f".{path.name}-{os.getpid()}.tmp"
    try:
        with temporary.open("xb") as stream:
            stream.write(encoded)
            stream.flush()
            os.fsync(stream.fileno())
        try:
            os.link(temporary, path)
        except FileExistsError:
            if path.read_bytes() != encoded:
                raise ReceiptError("Receipt publication collided with other content")
    finally:
        temporary.unlink(missing_ok=True)


def _segment_name(index: int) -> str:
    return f"operations-{index:06d}.json"


_SAFE_TOKEN = frozenset(
    "abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789-_."
)
_OPERATION_INDEX = "operations.index.json"
_OPERATION_SEGMENT_SIZE = 1_000
_RECEIPT_REF = re.compile(r"^apply-receipt:[^\s]+$")
