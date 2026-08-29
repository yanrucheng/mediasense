from __future__ import annotations

from copy import deepcopy
import json
from pathlib import Path

import pytest
from jsonschema import Draft202012Validator

from mediasense.apply import SourceEvidenceError, SourceItemEvidence


ROOT = Path(__file__).parents[1]
PRECHECK_TOOL = (
    ROOT
    / "docs"
    / "spec"
    / "spec-260826-1546-precheck-read"
    / "precheck-read.tool.json"
)


def _source_item_validator() -> Draft202012Validator:
    tool = json.loads(PRECHECK_TOOL.read_text(encoding="utf-8"))
    output = tool["outputSchema"]
    schema = {
        "$schema": "https://json-schema.org/draft/2020-12/schema",
        "$ref": "#/$defs/source_item_view",
        "$defs": output["$defs"],
    }
    return Draft202012Validator(schema)


def _verified_source_item() -> dict:
    return {
        "kind": "source_item",
        "ref": "source-item:gate-probe",
        "locator": {
            "kind": "source_root_relative_path",
            "source_root_ref": "source-root:gate-probe",
            "value": "camera/item.jpg",
        },
        "observations": [
            {
                "name": "source_content_verification",
                "status": "available",
                "value": {
                    "profile": "sha256-full-v1",
                    "value": "sha256:" + "0" * 64,
                    "size_bytes": 1,
                    "observed_at": "2026-08-30T00:00:00+08:00",
                    "producer": "contract-gate-probe-v1",
                },
                "basis": "Immutable evidence sealed by the exact PreCheck Result.",
            }
        ],
    }


def test_apply_consumer_conforms_to_accepted_precheck_verification_shape() -> None:
    item = _verified_source_item()
    _source_item_validator().validate(item)

    evidence = SourceItemEvidence.from_precheck_view(
        result_ref="precheck-result:gate-probe",
        view=item,
    )

    assert evidence.source_item_ref == "source-item:gate-probe"
    assert evidence.source_root_ref == "source-root:gate-probe"
    assert evidence.relative_path == "camera/item.jpg"
    assert evidence.verification.profile == "sha256-full-v1"
    assert evidence.verification.size_bytes == 1
    assert evidence.verification.producer == "contract-gate-probe-v1"


def test_precheck_schema_allows_unverified_items_but_apply_selection_rejects_them() -> (
    None
):
    item = _verified_source_item()
    item.pop("observations")

    # PreCheck intentionally accounts for excluded, unsupported, invalid, error,
    # unresolved, and otherwise non-selected Source Items without requiring proof.
    _source_item_validator().validate(item)
    with pytest.raises(SourceEvidenceError) as raised:
        SourceItemEvidence.from_precheck_view(
            result_ref="precheck-result:gate-probe",
            view=item,
        )
    assert raised.value.code == "source_verification_missing"


def test_replaceable_profile_remains_open_but_apply_support_is_fail_closed() -> None:
    item = deepcopy(_verified_source_item())
    item["observations"][0]["value"]["profile"] = "future-proof-v2"

    # The public contract leaves algorithms replaceable. Apply must explicitly
    # implement a profile before a selected move can use it.
    _source_item_validator().validate(item)
    with pytest.raises(SourceEvidenceError) as raised:
        SourceItemEvidence.from_precheck_view(
            result_ref="precheck-result:gate-probe",
            view=item,
        )
    assert raised.value.code == "source_verification_profile_unsupported"
