from __future__ import annotations

from copy import deepcopy
from datetime import datetime, timezone
import inspect
import json
from pathlib import Path

from PIL import Image
from jsonschema import Draft202012Validator

from mediasense.apply import ApplyRunTool
from mediasense.frozen_plan import content_identity
from mediasense.plan import ConfirmationContext, PlanWorkTool
from mediasense.precheck import (
    AccountingStore,
    ImageRenditionProducer,
    PrecheckReadTool,
    ResultStore,
)


ROOT = Path(__file__).parents[1]
APPLY_SPEC = ROOT / "docs" / "spec" / "spec-260829-0050-apply"
FROZEN_PLAN_SCHEMA = (
    ROOT / "docs" / "spec" / "spec-260827-1138-frozen-plan" / "frozen-plan.schema.json"
)


class RecordingPrecheckRead:
    name = "mediasense.precheck.read"

    def __init__(self, tool: PrecheckReadTool) -> None:
        self.tool = tool
        self.calls: list[dict[str, object]] = []

    def read(self, request: dict[str, object]) -> dict[str, object]:
        self.calls.append(deepcopy(request))
        return self.tool.read(request)


class UnderreportingPrecheckRead(RecordingPrecheckRead):
    def read(self, request: dict[str, object]) -> dict[str, object]:
        response = super().read(request)
        if (
            request.get("operation") != "resolve"
            or request.get("source_set", {}).get("relation") != "accounts_for"
        ):
            return response
        tampered = deepcopy(response)
        tampered["members"] = []
        tampered["page"]["returned"] = 0
        return tampered


def test_public_precheck_plan_apply_prepare_handoff_has_no_hidden_protocol(
    tmp_path: Path,
) -> None:
    precheck_database = tmp_path / "precheck-state" / "working.sqlite3"
    source = tmp_path / "source"
    destination = tmp_path / "destination"
    source.mkdir()
    destination.mkdir()
    Image.new("RGB", (80, 40), "purple").save(source / "original.jpg")
    source_before = (source / "original.jpg").read_bytes()

    accounting = AccountingStore(precheck_database)
    accounting.register_dataset("dataset-stage-handoff")
    run_id = accounting.start_or_resume_run("dataset-stage-handoff", source)
    accounting.process_run(run_id)
    rendition = ImageRenditionProducer(precheck_database).produce(
        run_id, Path("original.jpg")
    )
    result = ResultStore(precheck_database).seal(
        ResultStore(precheck_database).build_minimal(run_id, [rendition.work.work_id])
    )
    read_boundary = RecordingPrecheckRead(PrecheckReadTool(precheck_database))
    accounts = read_boundary.read(
        {
            "result_ref": result.result_ref,
            "operation": "resolve",
            "source_set": {
                "kind": "precheck_relation",
                "origin": result.result_ref,
                "relation": "accounts_for",
                "direction": "outbound",
            },
        }
    )
    source_item_ref = str(accounts["members"][0]["source_item_ref"])
    source_view = read_boundary.read(
        {
            "result_ref": result.result_ref,
            "operation": "expand",
            "source_item_refs": [source_item_ref],
            "include": ["source_item"],
        }
    )["items"][0]["included"]["source_item"]
    source_root_ref = str(source_view["locator"]["source_root_ref"])

    plan_tool = PlanWorkTool(tmp_path / "plan-state", read_boundary)
    created = plan_tool.handle(
        {
            "action": "create",
            "result_ref": result.result_ref,
            "request_id": "request:e2e-plan-create",
        }
    )
    all_sources = {
        "kind": "precheck_relation",
        "origin": result.result_ref,
        "relation": "accounts_for",
        "direction": "outbound",
    }
    updated = plan_tool.handle(
        {
            "action": "update",
            "work_ref": created["work_ref"],
            "base_revision": created["revision"],
            "request_id": "request:e2e-plan-update",
            "candidate_content": {
                "result_ref": result.result_ref,
                "scope": all_sources,
                "logical_root": "Media",
                "groups": [
                    {
                        "relative_path": ["Verified"],
                        "members": all_sources,
                        "source_naming": {"default": "preserve_source_basename"},
                    }
                ],
                "other_outcomes": [],
            },
        }
    )
    assert updated["outcome"] == "ok", updated
    inspected = plan_tool.handle(
        {
            "action": "inspect",
            "work_ref": created["work_ref"],
            "revision": updated["revision"],
            "sections": ["validation"],
        }
    )
    candidate_identity = inspected["candidate_content_identity"]
    sealed = plan_tool.handle(
        {
            "action": "seal",
            "work_ref": created["work_ref"],
            "revision": updated["revision"],
            "candidate_content_identity": candidate_identity,
            "request_id": "request:e2e-plan-seal",
        },
        confirmation=ConfirmationContext(
            principal_ref="human:e2e",
            confirmed_content_identity=candidate_identity,
            confirmed_at=datetime(2026, 8, 30, 16, 0, tzinfo=timezone.utc),
        ),
    )
    assert sealed["outcome"] == "ok"
    assert "frozen_plan" in sealed
    assert "artifact_path" not in sealed

    apply_tool = ApplyRunTool(
        tmp_path / "apply-state",
        read_boundary,
        run_schema_path=APPLY_SPEC / "apply-run.tool.json",
        frozen_plan_schema_path=FROZEN_PLAN_SCHEMA,
        receipt_schema_path=APPLY_SPEC / "apply-receipt.schema.json",
    )
    prepare_request = {
        "action": "prepare",
        "request_id": "request:e2e-apply-prepare",
        "forward": {
            "frozen_plan": sealed["frozen_plan"],
            "effect": "move_originals",
            "current_source_roots": [
                {
                    "source_root_ref": source_root_ref,
                    "current_root": str(source),
                }
            ],
            "destination_parent": str(destination),
        },
    }
    prepared = apply_tool.handle(prepare_request)
    status = apply_tool.handle({"action": "status", "run_ref": prepared["run_ref"]})

    assert prepared["outcome"] == "ok"
    assert status["state"] == "ready_for_authorization"
    assert status["summary"]["plan_scope_items"] == 1
    assert status["summary"]["materialization_operations"] == 1
    assert "frozen_plan_path" not in str(prepare_request)
    assert all(call["result_ref"] == result.result_ref for call in read_boundary.calls)
    assert all(
        call["operation"] in {"review", "expand", "resolve"}
        for call in read_boundary.calls
    )
    assert (source / "original.jpg").read_bytes() == source_before
    assert list(destination.iterdir()) == []

    assert "resolve_source_set" not in inspect.signature(ApplyRunTool).parameters

    output_validator = Draft202012Validator(
        json.loads((APPLY_SPEC / "apply-run.tool.json").read_text(encoding="utf-8"))[
            "outputSchema"
        ]
    )
    for case in ("extra_field", "unknown_profile"):
        invalid_plan = deepcopy(sealed["frozen_plan"])
        if case == "extra_field":
            invalid_plan["sealed_content"]["unexpected"] = "forbidden"
            identity = content_identity(invalid_plan["sealed_content"])
            invalid_plan["seal"]["content_identity"] = identity
            invalid_plan["seal"]["final_confirmation"]["confirmed_content_identity"] = (
                identity
            )
        else:
            invalid_plan["seal"]["encoding_profile"] = "future-profile"
        rejected = apply_tool.handle(
            {
                "action": "prepare",
                "request_id": f"request:e2e-reject-{case}",
                "forward": {
                    "frozen_plan": invalid_plan,
                    "effect": "move_originals",
                    "current_source_roots": [
                        {
                            "source_root_ref": source_root_ref,
                            "current_root": str(source),
                        }
                    ],
                    "destination_parent": str(destination),
                },
            }
        )
        assert rejected["outcome"] == "error"
        output_validator.validate(rejected)

    dishonest_apply = ApplyRunTool(
        tmp_path / "apply-state-dishonest-read",
        UnderreportingPrecheckRead(PrecheckReadTool(precheck_database)),
        run_schema_path=APPLY_SPEC / "apply-run.tool.json",
        frozen_plan_schema_path=FROZEN_PLAN_SCHEMA,
        receipt_schema_path=APPLY_SPEC / "apply-receipt.schema.json",
    )
    incomplete = dishonest_apply.handle(
        {
            "action": "prepare",
            "request_id": "request:e2e-incomplete-source-set",
            "forward": {
                "frozen_plan": sealed["frozen_plan"],
                "effect": "move_originals",
                "current_source_roots": [
                    {
                        "source_root_ref": source_root_ref,
                        "current_root": str(source),
                    }
                ],
                "destination_parent": str(destination),
            },
        }
    )
    assert incomplete["outcome"] == "error"
    assert incomplete["error"]["code"] == "invalid_request"
    output_validator.validate(incomplete)
    assert (source / "original.jpg").read_bytes() == source_before
    assert list(destination.iterdir()) == []
