"""100000 synthetic sealed occurrences: bounded readback and exact public paging.

This fixture exercises the immutable reader, not media acquisition or models.
"""

from copy import deepcopy
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import sqlite3

import pytest

from mediasense.precheck import AccountingStore, PrecheckReadTool
from mediasense.precheck._preparation import canonical


pytestmark = pytest.mark.scale


def test_hundred_thousand_profile_members_read_back_and_page_exactly(tmp_path):
    count = 100000
    database = tmp_path / "workspace/work.sqlite3"
    AccountingStore(database).register_dataset("large-scope")
    vector = json.loads(
        (
            Path(__file__).parents[2]
            / "docs/spec/contract/precheck-run/composition.mock.json"
        ).read_text()
    )["configuration_vectors"][0]
    result_ref = "precheck-result:large-scope"
    source_refs = [f"source-item:{i:06}" for i in range(count)]
    profile = {
        "configuration_identity": vector["identity"],
        "compression": None,
        "overrides": [
            {"source_set": {"kind": "profile_scope", "index": 0}, "compression": None}
        ],
    }
    boundary = {
        "source_read_only": True,
        "network_access": False,
        "remote_models": False,
        "billable_calls": 0,
    }
    package = {
        "schema_version": 2,
        "published_at": datetime.now(timezone.utc).isoformat(),
        "result": {
            "kind": "result",
            "ref": result_ref,
            "dataset_ref": "dataset:large-scope",
            "integrity": "valid",
            "coverage": "complete",
            "readiness": "blocked",
            "execution_boundary": boundary,
            "qualifications": [
                {
                    "code": "synthetic_unresolved",
                    "effect": "blocks_use",
                    "message": "Synthetic unprepared source records for bounded reading acceptance.",
                }
            ],
        },
        "dataset": {"kind": "dataset", "ref": "dataset:large-scope"},
        "sources": [],
        "evidence": [],
        "relationships": [],
        "artifact_refs": [],
        "execution_boundary": boundary,
        "preparation": {
            "profile": profile,
            "configuration": vector["value"],
            "scopes": [source_refs],
        },
        "input_bindings": {
            "result_ref": "precheck-result:synthetic-input",
            "digest": "1" * 64,
            "members": [],
        },
    }
    for index, ref in enumerate(source_refs):
        locator = {
            "kind": "source_root_relative_path",
            "source_root_ref": "source-root:synthetic",
            "value": f"{index:06}.jpg",
        }
        package["sources"].append(
            {
                "relative_path": locator["value"],
                "view": {"kind": "source_item", "ref": ref, "locator": locator},
            }
        )
        package["relationships"].append(
            {
                "origin": result_ref,
                "relation": "accounts_for",
                "target_kind": "source_item",
                "member": {
                    "target": ref,
                    "scope": "source_media",
                    "condition": "unresolved",
                },
            }
        )
        package["input_bindings"]["members"].append(
            {
                "input_ref": f"source-item:prior-{index:06}",
                "target_ref": ref,
                "locator": locator,
                "verification": {"profile": None, "value": "", "status": "unavailable"},
            }
        )
    encoded = canonical(package).encode()
    path = database.parent / "large.json"
    path.write_bytes(encoded)
    with sqlite3.connect(database) as connection:
        connection.execute(
            "INSERT INTO sealed_results (result_ref,dataset_id,relative_path,digest_algorithm,digest,size_bytes,published_at) VALUES (?,?,?,'sha256',?,?,?)",
            (
                result_ref,
                "large-scope",
                path.name,
                hashlib.sha256(encoded).hexdigest(),
                len(encoded),
                package["published_at"],
            ),
        )
    del package, encoded
    reader = PrecheckReadTool(database)
    base = {"dataset_ref": "dataset:large-scope", "result_ref": result_ref}
    review = reader.read({**base, "action": "review", "include": ["preparation"]})
    assert "error" not in review, review
    assert review["preparation"]["profile"] == profile
    assert len(canonical(review).encode()) < 4096
    selection = {"kind": "profile_scope", "index": 0}
    request = {
        **base,
        "action": "resolve",
        "source_set": selection,
        "page": {"limit": 1000},
    }
    refs, cursors, identity = [], set(), None
    while True:
        page = reader.read(request)
        assert "error" not in page, page
        assert page["page"]["total"] == count
        if identity is not None:
            assert page["resolution"]["membership_identity"] == identity
        identity = page["resolution"]["membership_identity"]
        refs.extend(m["source_item_ref"] for m in page["members"])
        cursor = page["page"]["next_cursor"]
        if cursor is None:
            break
        assert cursor not in cursors and page["members"]
        cursors.add(cursor)
        if len(cursors) == 1:
            altered = deepcopy(request)
            altered["page"] = {"limit": 999, "cursor": cursor}
            assert reader.read(altered)["error"]["code"] == "invalid_cursor"
        request["page"]["cursor"] = cursor
    assert refs == source_refs
    assert (
        identity
        == "sha256:"
        + hashlib.sha256(
            canonical(
                {"result_ref": result_ref, "source_set": selection, "members": refs}
            ).encode()
        ).hexdigest()
    )
