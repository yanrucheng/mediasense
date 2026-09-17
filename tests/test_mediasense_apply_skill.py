from __future__ import annotations

from datetime import datetime, timezone
import json
from pathlib import Path

from mediasense.apply import (
    ApplyConfirmationContext,
    ApplyExecutor,
    ApplyReceiptReader,
    ApplyRunTool,
)
from mediasense.apply.filesystem import EffectObservation, FilesystemEffectError
from test_apply_preparation import _fixture, _plan


ROOT = Path(__file__).parents[1]
APPLY_SPEC = ROOT / "docs" / "spec" / "contract/apply"
APPLY_SKILL = (
    ROOT
    / "src"
    / "mediasense"
    / "_resources"
    / "skills"
    / "mediasense-apply"
    / "SKILL.md"
)
FROZEN_PLAN_SCHEMA = (
    ROOT / "docs" / "spec" / "contract/frozen-plan" / "frozen-plan.schema.json"
)
WORKFLOWS = json.loads(
    (ROOT / "tests" / "fixtures" / "apply-skill-workflows-v1.json").read_text(
        encoding="utf-8"
    )
)["scenarios"]


def test_skill_uses_direct_frozen_plan_handoff_and_no_geo() -> None:
    skill = APPLY_SKILL.read_text(encoding="utf-8")
    assert "exact `frozen_plan` object returned by Plan seal" in skill
    assert "Do not request, refresh, or interpret geographic evidence" in skill


class _FailFirstItemOnce:
    def __init__(self) -> None:
        self.failed = False

    def move(self, **kwargs) -> EffectObservation:
        source = kwargs["source"]
        target = kwargs["target"]
        if source.name == "a.jpg" and not self.failed:
            self.failed = True
            raise FilesystemEffectError(
                "temporary_read_failure", "controlled transient fixture failure"
            )
        target.parent.mkdir(parents=True, exist_ok=True)
        source.rename(target)
        return EffectObservation(
            status="completed",
            bytes_moved=kwargs["expected_size"],
            source_after="absent",
            target_after="verified_present",
            verification_profile="same_filesystem_identity_and_location",
            verification_basis="Controlled fixture move verified.",
        )

    def reconcile(self, **_kwargs) -> EffectObservation:
        raise AssertionError("the controlled failure leaves no pending intent")


def _new_tool(tmp_path: Path):
    source, destination, _state, files, precheck_read = _fixture(tmp_path)
    tool = ApplyRunTool(
        tmp_path / "apply-store",
        precheck_read,
        run_schema_path=APPLY_SPEC / "apply-run.tool.json",
        frozen_plan_schema_path=FROZEN_PLAN_SCHEMA,
        receipt_schema_path=APPLY_SPEC / "apply-receipt.schema.json",
    )
    return tool, _plan(), source, destination, files, precheck_read


def _prepare(tool: ApplyRunTool, frozen_plan: dict, source: Path, destination: Path):
    response = tool.handle(
        {
            "action": "prepare",
            "request_id": "request:skill-prepare",
            "forward": {
                "frozen_plan": frozen_plan,
                "effect": "move_originals",
                "current_source_roots": [
                    {
                        "source_root_ref": "source-root:test",
                        "current_root": str(source),
                    }
                ],
                "destination_parent": str(destination),
            },
        }
    )
    return tool.handle({"action": "status", "run_ref": response["run_ref"]})


def _authorize(tool: ApplyRunTool, status: dict[str, object], request_id: str):
    identity = str(status["prepared_content_identity"])
    return tool.handle(
        {
            "action": "execute",
            "run_ref": status["run_ref"],
            "prepared_revision": status["prepared_revision"],
            "prepared_content_identity": identity,
            "request_id": request_id,
        },
        confirmation=ApplyConfirmationContext(
            principal_ref="human:skill-fixture",
            confirmed_content_identity=identity,
            confirmed_at=datetime(2026, 8, 30, 3, 0, tzinfo=timezone.utc),
        ),
    )


def _reader(tool: ApplyRunTool) -> ApplyReceiptReader:
    return ApplyReceiptReader(tool.receipt_store, APPLY_SPEC / "apply-read.tool.json")


def _scenario(name: str) -> dict[str, object]:
    return next(value for value in WORKFLOWS if value["name"] == name)


def test_skill_forward_workflow_reaches_receipt_and_freshly_authorized_rewind(
    tmp_path: Path,
) -> None:
    expected = _scenario("forward_receipt_and_rewind")
    tool, frozen_plan, source, destination, files, _precheck = _new_tool(tmp_path)
    checkpoints = []

    status = _prepare(tool, frozen_plan, source, destination)
    assert status["state"] == "ready_for_authorization"
    assert status["allowed_actions"] == ["execute", "cancel"]
    checkpoints.append("request_exact_confirmation")
    accepted = _authorize(tool, status, "request:skill-execute")
    assert accepted["target_state"] == "executing"
    checkpoints.append("observe_execution")

    closed = tool.run_pending(str(status["run_ref"]))
    assert closed["state"] == "closed"
    receipt_ref = closed["published_receipt"]["receipt_ref"]
    receipt = _reader(tool).read({"receipt_ref": receipt_ref, "action": "inspect"})
    assert receipt["receipt"]["completion"] == "complete"
    assert (destination / "Media" / "Trip" / "a.jpg").read_bytes() == files["a.jpg"]
    checkpoints.append("read_receipt")

    rewind = tool.handle(
        {
            "action": "prepare",
            "request_id": "request:skill-rewind-prepare",
            "rewind": {"receipt_ref": receipt_ref},
        }
    )
    rewind_status = tool.handle({"action": "status", "run_ref": rewind["run_ref"]})
    assert rewind_status["state"] == "ready_for_authorization"
    assert rewind_status["summary"]["execution_binding"]["kind"] == "rewind"
    checkpoints.append("request_fresh_rewind_confirmation")
    _authorize(tool, rewind_status, "request:skill-rewind-execute")
    rewind_closed = tool.run_pending(str(rewind_status["run_ref"]))
    rewind_receipt = _reader(tool).read(
        {
            "receipt_ref": rewind_closed["published_receipt"]["receipt_ref"],
            "action": "inspect",
        }
    )
    assert rewind_receipt["receipt"]["execution_binding"]["kind"] == "rewind"
    assert (source / "a.jpg").read_bytes() == files["a.jpg"]
    checkpoints.append("read_rewind_receipt")
    assert checkpoints == expected["expected_agent_checkpoints"]


def test_skill_blocks_missing_precheck_proof(
    tmp_path: Path,
) -> None:
    expected = _scenario("prepare_without_precheck_proof")
    tool, frozen_plan, source, destination, _files, precheck = _new_tool(tmp_path)
    precheck.views["source-item:a"].pop("observations")
    checkpoints = []

    status = _prepare(tool, frozen_plan, source, destination)
    assert status["state"] == "blocked"
    assert not (destination / "Media").exists()
    assert (source / "a.jpg").exists()
    checkpoints.append("explain_missing_source_evidence")
    cancelled = tool.handle({"action": "cancel", "run_ref": status["run_ref"]})
    assert cancelled["target_state"] == "cancelled"
    assert not (destination / "Media").exists()
    checkpoints.append("cancel_without_effect")
    assert checkpoints == expected["expected_agent_checkpoints"]


def test_skill_reports_effect_boundary_drift_without_blind_retry(
    tmp_path: Path,
) -> None:
    expected = _scenario("effect_boundary_drift")
    tool, frozen_plan, source, destination, _files, _precheck = _new_tool(tmp_path)
    checkpoints = []
    status = _prepare(tool, frozen_plan, source, destination)
    checkpoints.append("request_exact_confirmation")
    (source / "a.jpg").write_bytes(b"changed after Human review")
    _authorize(tool, status, "request:skill-drift-execute")
    checkpoints.append("observe_execution")

    stopped = tool.run_pending(str(status["run_ref"]))
    assert stopped["state"] == "needs_attention"
    assert any(reason["code"] == "source_stale" for reason in stopped["reasons"])
    assert (source / "a.jpg").exists()
    assert not (destination / "Media" / "Trip" / "a.jpg").exists()
    checkpoints.append("explain_drift_and_reopen_upstream")
    assert checkpoints == expected["expected_agent_checkpoints"]


def test_skill_reports_partial_reality_then_resumes_allowed_run(
    tmp_path: Path,
) -> None:
    expected = _scenario("localized_failure_and_resume")
    tool, frozen_plan, source, destination, _files, _precheck = _new_tool(tmp_path)
    tool.executor = ApplyExecutor(
        tool.run_store,
        tool.receipt_store,
        filesystem=_FailFirstItemOnce(),
        clock=lambda: datetime(2026, 8, 30, 3, 0, tzinfo=timezone.utc),
    )
    checkpoints = []
    status = _prepare(tool, frozen_plan, source, destination)
    checkpoints.append("request_exact_confirmation")
    _authorize(tool, status, "request:skill-partial-execute")
    checkpoints.append("observe_execution")
    attention = tool.run_pending(str(status["run_ref"]))
    assert attention["state"] == "needs_attention"
    assert attention["progress"]["completed_and_verified"] == 1
    assert attention["progress"]["failed"] == 1
    assert attention["allowed_actions"] == ["resume", "cancel"]
    checkpoints.append("explain_partial_completion")

    resumed = tool.handle({"action": "resume", "run_ref": status["run_ref"]})
    assert resumed["target_state"] == "executing"
    checkpoints.append("resume_allowed_run")
    closed = tool.run_pending(str(status["run_ref"]))
    assert closed["state"] == "closed"
    inspected = _reader(tool).read(
        {
            "receipt_ref": closed["published_receipt"]["receipt_ref"],
            "action": "inspect",
        }
    )
    assert inspected["receipt"]["completion"] == "complete"
    checkpoints.append("read_receipt")
    assert checkpoints == expected["expected_agent_checkpoints"]
