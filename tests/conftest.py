import pytest


@pytest.fixture(autouse=True)
def plan_kernel_observation_clock(monkeypatch, request):
    # Kernel replay tests freeze only observation time. Runtime acceptance checks
    # changing delivery observations independently from persisted business receipts.
    if request.path.name not in {
        "test_plan_work.py",
        "test_plan_optional_work.py",
        "test_plan_update_execution.py",
        "test_plan_update_process.py",
        "test_plan_update_mcp.py",
    }:
        return
    import mediasense.plan.view as view
    from datetime import datetime, timezone

    class Clock:
        @staticmethod
        def now(tz=None):
            return datetime(2026, 9, 13, tzinfo=timezone.utc)

    monkeypatch.setattr(view, "datetime", Clock)
