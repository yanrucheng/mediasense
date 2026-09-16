"""Read-only audit of an existing Apply Receipt, sealed Plan and backed-up files.

Use the installed MediaSense interpreter. No RuntimeHost, Apply executor,
Dataset open, authorization or media write is invoked. Only --output is written.
The mutable Apply database is opened explicitly in SQLite read-only mode.
"""

from __future__ import annotations

import argparse
from collections import Counter
import ctypes
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import sqlite3
import stat
import sys
import time

from jsonschema import Draft202012Validator

from mediasense.apply.receipt import ApplyReceiptReader, ReceiptStore
from mediasense.precheck._fingerprint import hash_regular_file
from mediasense.precheck.read import PrecheckReadTool, bind_precheck_read
from mediasense.runtime.resources import schema_path
from mediasense.source_sets import ResultSourceSetResolver


def identity(value):
    encoded = json.dumps(
        value, ensure_ascii=False, sort_keys=True, separators=(",", ":")
    ).encode()
    return "sha256:" + hashlib.sha256(encoded).hexdigest()


def digest(path):
    with path.open("rb") as stream:
        return "sha256:" + hashlib.file_digest(stream, "sha256").hexdigest()


def files(root):
    return {
        str(path.relative_to(root)): path
        for path in root.rglob("*")
        if path.is_file() or path.is_symlink()
    }


def xattrs(path):
    if hasattr(os, "listxattr"):
        return {
            name: hashlib.sha256(os.getxattr(path, name)).hexdigest()
            for name in os.listxattr(path)
        }
    if sys.platform != "darwin":
        raise RuntimeError("No read-only extended attribute reader for this platform")
    # CPython's os xattr API is Linux-only in this installed interpreter.
    library = ctypes.CDLL(None, use_errno=True)
    listing = library.listxattr
    listing.argtypes = [ctypes.c_char_p, ctypes.c_void_p, ctypes.c_size_t, ctypes.c_int]
    listing.restype = ctypes.c_ssize_t
    reading = library.getxattr
    reading.argtypes = [
        ctypes.c_char_p,
        ctypes.c_char_p,
        ctypes.c_void_p,
        ctypes.c_size_t,
        ctypes.c_uint32,
        ctypes.c_int,
    ]
    reading.restype = ctypes.c_ssize_t
    encoded = os.fsencode(path)
    size = listing(encoded, None, 0, 1)
    if size < 0:
        raise OSError(ctypes.get_errno(), "listxattr failed", str(path))
    buffer = ctypes.create_string_buffer(size)
    actual = listing(encoded, buffer, size, 1)
    if actual < 0:
        raise OSError(ctypes.get_errno(), "listxattr read failed", str(path))
    result = {}
    for name in filter(None, buffer.raw[:actual].split(b"\0")):
        size = reading(encoded, name, None, 0, 0, 1)
        if size < 0:
            raise OSError(ctypes.get_errno(), "getxattr failed", str(path))
        value = ctypes.create_string_buffer(size)
        actual = reading(encoded, name, value, size, 0, 1)
        if actual < 0:
            raise OSError(ctypes.get_errno(), "getxattr read failed", str(path))
        result[os.fsdecode(name)] = hashlib.sha256(value.raw[:actual]).hexdigest()
    return result


def metadata(path):
    value = path.stat()
    return {
        "mtime_ns": value.st_mtime_ns,
        "mode": stat.S_IMODE(value.st_mode),
        "uid": value.st_uid,
        "gid": value.st_gid,
        "flags": getattr(value, "st_flags", None),
        "birthtime": getattr(value, "st_birthtime", None),
        "xattrs": xattrs(path),
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--config", type=Path, default=Path(__file__).with_name("config.json")
    )
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    config = json.loads(args.config.read_text())
    workspace = Path(config["workspace"])
    source_root = Path(config["source_root"])
    backup_root = Path(config["backup_root"])
    receipt_ref = config["receipt_ref"]
    started = time.monotonic()

    store = ReceiptStore(
        workspace / "apply/receipts", schema_path("apply-receipt.schema.json")
    )
    receipt = store.read(receipt_ref)
    content = receipt["sealed_content"]
    assert identity(content) == receipt["seal"]["content_identity"]
    reader = ApplyReceiptReader(store, schema_path("apply-read.tool.json"))
    inspected = reader.read({"action": "inspect", "receipt_ref": receipt_ref})
    assert inspected["outcome"] == "ok", inspected
    operations = []
    pages = 0
    cursor = None
    while True:
        page = {"limit": 1000}
        if cursor is not None:
            page["cursor"] = cursor
        response = reader.read(
            {
                "action": "traverse",
                "receipt_ref": receipt_ref,
                "section": "operations",
                "page": page,
            }
        )
        assert response["outcome"] == "ok", response
        operations.extend(response["items"])
        pages += 1
        if response["page"]["complete"]:
            assert len(operations) == response["page"]["total"]
            break
        assert response["page"]["next_cursor"] != cursor
        cursor = response["page"]["next_cursor"]
    assert len({item["source_item_ref"] for item in operations}) == len(operations)
    assert len({item["intended_target"] for item in operations}) == len(operations)

    plan_path = workspace / config["frozen_plan"]
    plan = json.loads(plan_path.read_text())
    frozen = plan["sealed_content"]
    Draft202012Validator(
        json.loads(schema_path("frozen-plan.schema.json").read_text())
    ).validate(plan)
    assert identity(frozen) == plan["seal"]["content_identity"]
    assert plan["seal"]["final_confirmation"]["confirmed_content_identity"] == identity(
        frozen
    )
    assert frozen["plan_ref"] == content["frozen_plan_ref"]
    assert identity(frozen) == content["frozen_plan_content_identity"]
    boundary = bind_precheck_read(
        PrecheckReadTool(workspace / "precheck/work.sqlite3"), config["dataset_ref"]
    )
    resolver = ResultSourceSetResolver(frozen["result_ref"], boundary)
    scope = resolver.resolve(frozen["scope"])
    assignments = {}
    target_root = Path(
        content["execution_binding"]["destination"]["resolved_logical_root"]
    )
    assert target_root.name == frozen["logical_root"]
    for group in frozen["groups"]:
        overrides = {
            value["source_item_ref"]: value["name"]
            for value in group["source_naming"].get("overrides", [])
        }
        for ref in resolver.resolve(group["members"]):
            assert ref not in assignments
            assignments[ref] = (
                target_root.joinpath(*group["relative_path"]),
                overrides.get(ref),
            )
    accounted = set(assignments)
    outcome_counts = {}
    for outcome in frozen["other_outcomes"]:
        members = resolver.resolve(outcome["members"])
        assert not accounted.intersection(members)
        accounted.update(members)
        outcome_counts[outcome["outcome"]] = len(members)
    assert accounted == scope
    assert set(assignments) == {item["source_item_ref"] for item in operations}
    print(
        "Plan/Result membership and Receipt pagination verified",
        file=sys.stderr,
        flush=True,
    )

    # Public resolve already carries locators and the declared verification
    # profile. Reuse those verified pages; detailed photographic observations
    # are irrelevant to this audit and can exceed expand's byte budget.
    source_views = resolver.source_views
    assert set(source_views) == set(scope)

    uri = (workspace / "apply/work.sqlite3").as_uri() + "?mode=ro"
    with sqlite3.connect(uri, uri=True) as connection:
        connection.row_factory = sqlite3.Row
        run = dict(
            connection.execute(
                "SELECT * FROM runs WHERE run_ref = ?", (content["run_ref"],)
            ).fetchone()
        )
        prepared = {
            row["source_item_ref"]: dict(row)
            for row in connection.execute(
                "SELECT * FROM run_items WHERE run_ref = ?", (content["run_ref"],)
            )
        }
    assert run["state"] == "closed"
    assert run["receipt_content_identity"] == receipt["seal"]["content_identity"]
    assert set(prepared) == set(scope)
    assert (
        run["authorized_prepared_content_identity"]
        == content["prepared_content_identity"]
    )

    backup_files = files(backup_root)
    after_files = files(source_root)
    target_files = files(target_root)
    moved_relative = set()
    planned_targets = set()
    anomalies = []
    metadata_differences = Counter()
    precheck_verification_profiles = Counter()
    total_moved_bytes = 0
    for item in operations:
        ref = item["source_item_ref"]
        original = Path(item["source_before"])
        target = Path(item["intended_target"])
        relative = str(original.relative_to(source_root))
        moved_relative.add(relative)
        planned_targets.add(str(target.relative_to(target_root)))
        view = source_views[ref]
        locator = view["locator"]
        assert locator["kind"] == "source_root_relative_path"
        assert source_root / locator["value"] == original
        directory, override = assignments[ref]
        assert target == directory / (override or original.name)
        observations = [
            value
            for value in view["observations"]
            if value["name"] == "source_content_verification"
        ]
        assert len(observations) == 1 and observations[0]["status"] == "available"
        upstream = observations[0]["value"]
        precheck_verification_profiles[upstream["profile"]] += 1
        expected = item["source_verification"]["expected_basis"]
        if upstream["profile"] == "sha256-full-v1":
            assert upstream["value"] == expected["value"]
            assert upstream["size_bytes"] == expected["size_bytes"]
        assert item["result"] == "completed_and_verified" and item["attempts"] == 1
        if original.exists() or original.is_symlink():
            anomalies.append({"kind": "moved_source_present", "path": relative})
        if not target.is_file() or target.is_symlink() or relative not in backup_files:
            anomalies.append(
                {"kind": "target_or_backup_missing_or_unsafe", "path": relative}
            )
            continue
        baseline = backup_files[relative]
        if upstream["profile"] == "candidate-sha256-full-or-3x4k-v1":
            observed = "sha256:" + hash_regular_file(baseline, baseline.stat())
            if (
                observed != upstream["value"]
                or baseline.stat().st_size != upstream["size_bytes"]
            ):
                anomalies.append(
                    {"kind": "precheck_fingerprint_mismatch", "path": relative}
                )
        elif upstream["profile"] != "sha256-full-v1":
            anomalies.append({"kind": "unsupported_precheck_profile", "path": relative})
        if digest(target) != expected["value"] or digest(baseline) != expected["value"]:
            anomalies.append({"kind": "content_mismatch", "path": relative})
        current = target.stat()
        pre = prepared[ref]
        if (current.st_dev, current.st_ino, current.st_size, current.st_mtime_ns) != (
            pre["observed_device"],
            pre["observed_inode"],
            pre["observed_size"],
            pre["observed_mtime_ns"],
        ):
            anomalies.append({"kind": "prepared_identity_changed", "path": relative})
        left, right = metadata(baseline), metadata(target)
        for key in left:
            if left[key] != right[key]:
                metadata_differences[key] += 1
        total_moved_bytes += current.st_size
    print(
        "Moved targets and backup bytes verified; checking retained files",
        file=sys.stderr,
        flush=True,
    )
    remaining = set(backup_files) - moved_relative
    for relative in sorted(remaining):
        if relative not in after_files or digest(after_files[relative]) != digest(
            backup_files[relative]
        ):
            anomalies.append({"kind": "retained_missing_or_changed", "path": relative})
    missing_backups = moved_relative - set(backup_files)
    section_counts = {}
    for section in ("exceptions", "metadata_discrepancies", "created_directories"):
        response = reader.read(
            {
                "action": "traverse",
                "receipt_ref": receipt_ref,
                "section": section,
                "page": {"limit": 1000},
            }
        )
        assert response["outcome"] == "ok" and response["page"]["complete"]
        section_counts[section] = response["page"]["total"]
    result = {
        "observed_at": datetime.now(timezone.utc).isoformat(),
        "receipt_ref": receipt_ref,
        "receipt_identity": receipt["seal"]["content_identity"],
        "receipt_inspect": inspected["receipt"],
        "receipt_operation_pages": pages,
        "receipt_section_counts": section_counts,
        "plan_ref": frozen["plan_ref"],
        "frozen_plan_identity": identity(frozen),
        "frozen_plan_bytes": plan_path.stat().st_size,
        "plan_groups": len(frozen["groups"]),
        "scope_items": len(scope),
        "outcome_counts": outcome_counts,
        "moved_files": len(operations),
        "moved_bytes": total_moved_bytes,
        "moved_extensions": dict(
            Counter(Path(item["intended_target"]).suffix.lower() for item in operations)
        ),
        "backup_files": len(backup_files),
        "backup_bytes": sum(path.stat().st_size for path in backup_files.values()),
        "remaining_files_verified": len(remaining),
        "source_files_now": len(after_files),
        "target_files_now": len(target_files),
        "unplanned_current_source_files": sorted(set(after_files) - remaining),
        "unplanned_current_target_files": sorted(set(target_files) - planned_targets),
        "missing_backup_paths": sorted(missing_backups),
        "metadata_differences_against_backup": dict(metadata_differences),
        "precheck_verification_profiles": dict(precheck_verification_profiles),
        "anomalies": anomalies,
        "resource_facts": content["resource_facts"],
        "audit_seconds": round(time.monotonic() - started, 3),
        "media_mutations": 0,
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n")
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return int(bool(anomalies or missing_backups))


if __name__ == "__main__":
    raise SystemExit(main())
