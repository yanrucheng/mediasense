from __future__ import annotations

from copy import deepcopy
import json
from pathlib import Path

from jsonschema import Draft202012Validator
import pytest
from mediasense.apply.preparation import SourceEvidenceError

from mediasense.apply import SourceItemEvidence


ROOT = Path(__file__).parents[1]
PRECHECK_TOOL = (
    ROOT / "docs" / "spec" / "contract/precheck-read" / "precheck-read.tool.json"
)


def _validate_public_source_item(item: dict) -> None:
    tool = json.loads(PRECHECK_TOOL.read_text(encoding="utf-8"))
    schema = {
        "$defs": tool["outputSchema"]["$defs"],
        "$ref": "#/$defs/source_expansion_item",
    }
    Draft202012Validator(schema).validate(
        {
            "source_item_ref": item["ref"],
            "included": {
                "source_item": {"locator": item["locator"]},
                "observations": item.get("observations", []),
            },
        }
    )


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
    _validate_public_source_item(item)

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


def test_apply_refuses_missing_old_evidence() -> None:
    item = _verified_source_item()
    item.pop("observations")
    _validate_public_source_item(item)
    with pytest.raises(SourceEvidenceError, match="no available immutable"):
        SourceItemEvidence.from_precheck_view(
            result_ref="precheck-result:gate-probe", view=item
        )


def test_apply_refuses_unknown_old_evidence_profile() -> None:
    item = deepcopy(_verified_source_item())
    item["observations"][0]["value"]["profile"] = "future-proof-v2"
    _validate_public_source_item(item)
    with pytest.raises(SourceEvidenceError, match="unsupported"):
        SourceItemEvidence.from_precheck_view(
            result_ref="precheck-result:gate-probe", view=item
        )
