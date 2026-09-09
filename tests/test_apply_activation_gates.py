from __future__ import annotations

from copy import deepcopy
import json
from pathlib import Path

from jsonschema import Draft202012Validator

from mediasense.apply import SourceItemEvidence


ROOT = Path(__file__).parents[1]
PRECHECK_TOOL = (
    ROOT
    / "docs"
    / "spec"
    / "contract/precheck-read"
    / "precheck-read.tool.json"
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


def test_apply_can_establish_exact_proof_when_precheck_has_no_verification() -> None:
    item = _verified_source_item()
    item.pop("observations")

    # PreCheck intentionally accounts for excluded, unsupported, invalid, error,
    # unresolved, and otherwise non-selected Source Items without requiring proof.
    _validate_public_source_item(item)
    evidence = SourceItemEvidence.from_precheck_view(
        result_ref="precheck-result:gate-probe",
        view=item,
    )
    assert evidence.verification is None


def test_unknown_precheck_profile_does_not_block_fresh_apply_proof() -> None:
    item = deepcopy(_verified_source_item())
    item["observations"][0]["value"]["profile"] = "future-proof-v2"

    # The public contract leaves algorithms replaceable. An unsupported
    # PreCheck profile is not treated as exact evidence; Apply establishes its
    # own supported exact proof before authorization.
    _validate_public_source_item(item)
    evidence = SourceItemEvidence.from_precheck_view(
        result_ref="precheck-result:gate-probe",
        view=item,
    )
    assert evidence.verification is None
