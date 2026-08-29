from __future__ import annotations

from io import BytesIO
from pathlib import Path

from PIL import Image
import pytest

from mediasense.precheck import (
    AccountingStore,
    PrecheckReadTool,
    PrecheckRunTool,
    WorkStore,
)
from mediasense.precheck._orchestrator import PrecheckExecutionConfig


pytestmark = pytest.mark.scale


def test_five_hundred_to_three_to_two_hundred_sealed_results(
    tmp_path: Path,
) -> None:
    database = tmp_path / "workspace" / "working.sqlite3"
    source = tmp_path / "source"
    source.mkdir()
    encoded = BytesIO()
    Image.new("RGB", (8, 8), "blue").save(encoded, format="JPEG")
    source_bytes = encoded.getvalue()
    for index in range(500):
        (source / f"item-{index:03d}.jpg").write_bytes(source_bytes)
    accounting = AccountingStore(database)
    accounting.register_dataset("scale-500")
    reader = PrecheckReadTool(database)
    result_refs: list[str] = []
    entry_totals: list[int] = []
    rendition_ids: list[set[str]] = []

    for sequence, target in enumerate((500, 3, 200), start=1):
        accounting_run_id = accounting.start_or_resume_run("scale-500", source)
        tool = PrecheckRunTool(
            database,
            execution_config=PrecheckExecutionConfig(
                metadata=False,
                gpx=False,
                video=False,
                bundles=False,
                compression_target=target,
            ),
        )
        started = tool.run(
            {
                "action": "start",
                "dataset_ref": "dataset:scale-500",
                "request_id": f"request:scale-{sequence}",
            }
        )
        tool.advance(str(started["run_ref"]))
        status = tool.run({"action": "status", "run_ref": started["run_ref"]})
        assert status["state"] == "completed"
        result_ref = str(status["published_result"]["result_ref"])
        result_refs.append(result_ref)
        rendition_ids.append(
            {
                work.work_id
                for work in WorkStore(database).list_run_work(accounting_run_id)
                if work.spec.capability == "image-rendition"
            }
        )
        page = reader.read(
            {
                "action": "traverse",
                "direction": "outbound",
                "page": {"limit": 1},
                "relation": "entry_evidence",
                "result_ref": result_ref,
            }
        )
        entry_totals.append(page["page"]["total"])

    assert entry_totals == [500, 3, 200]
    assert len(set(result_refs)) == 3
    assert len(rendition_ids[0]) == 500
    assert rendition_ids[1:] == [rendition_ids[0], rendition_ids[0]]
    assert all(path.read_bytes() == source_bytes for path in source.glob("*.jpg"))
