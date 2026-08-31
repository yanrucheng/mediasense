from __future__ import annotations

import sqlite3
from pathlib import Path

from mediasense.dataset_reference import dataset_id_from_ref
from mediasense.runtime.host import RuntimeHost


def test_composition_root_constructs_all_tools_offline(tmp_path: Path) -> None:
    source = tmp_path / "source"
    source.mkdir()
    host = RuntimeHost()
    opened = host.open_dataset(str(source), str(tmp_path / "workspace"))

    assert opened["outcome"] == "ok"
    assert [item["name"] for item in host.tools()] == [
        "mediasense.dataset.open",
        "mediasense.precheck.run",
        "mediasense.precheck.read",
        "mediasense.plan.work",
        "mediasense.geo.query",
        "mediasense.apply.run",
        "mediasense.apply.read",
    ]


def test_opened_dataset_can_start_precheck_immediately(tmp_path: Path) -> None:
    source = tmp_path / "source"
    source.mkdir()
    host = RuntimeHost()
    opened = host.open_dataset(str(source), str(tmp_path / "workspace"))
    dataset_ref = str(opened["dataset_ref"])

    started = host.call_tool(
        "mediasense.precheck.run",
        dataset_ref=dataset_ref,
        request={
            "action": "start",
            "dataset_ref": dataset_ref,
            "request_id": "request:runtime-first-use",
        },
    )

    assert started["outcome"] == "ok"
    assert str(started["run_ref"]).startswith("precheck-run:")
    assert started["dataset_ref"] == dataset_ref
    assert started["state"] == "running"


def test_reopen_repairs_legacy_prefixed_dataset_registration(
    tmp_path: Path,
) -> None:
    source = tmp_path / "source"
    source.mkdir()
    workspace = tmp_path / "workspace"
    original_host = RuntimeHost()
    opened = original_host.open_dataset(str(source), str(workspace))
    dataset_ref = str(opened["dataset_ref"])
    dataset_id = dataset_id_from_ref(dataset_ref)
    database = workspace / "precheck" / "work.sqlite3"
    with sqlite3.connect(database) as connection:
        connection.execute(
            "UPDATE datasets SET dataset_id = ? WHERE dataset_id = ?",
            (dataset_ref, dataset_id),
        )

    reopened_host = RuntimeHost()
    reopened = reopened_host.open_dataset(str(source), str(workspace))
    started = reopened_host.call_tool(
        "mediasense.precheck.run",
        dataset_ref=dataset_ref,
        request={
            "action": "start",
            "dataset_ref": dataset_ref,
            "request_id": "request:legacy-prefixed-dataset",
        },
    )

    assert reopened["outcome"] == "ok"
    assert reopened["created"] is False
    assert started["outcome"] == "ok"
    assert str(started["run_ref"]).startswith("precheck-run:")
    with sqlite3.connect(database) as connection:
        stored_ids = [
            str(row[0])
            for row in connection.execute(
                "SELECT dataset_id FROM datasets ORDER BY dataset_id"
            )
        ]
    assert stored_ids == [dataset_id]


def test_offline_geo_call_is_unavailable_without_provider_effect(
    tmp_path: Path,
) -> None:
    source = tmp_path / "source"
    source.mkdir()
    host = RuntimeHost()
    opened = host.open_dataset(str(source), str(tmp_path / "workspace"))

    result = host.call_tool(
        "mediasense.geo.query",
        dataset_ref=str(opened["dataset_ref"]),
        request={
            "request_id": "request:offline",
            "operation": "reverse_geocode",
            "subjects": [
                {
                    "subject_ref": "source-item:test",
                    "coordinate": {
                        "latitude": 22.3193,
                        "longitude": 114.1694,
                        "datum": "WGS84",
                    },
                }
            ],
            "locale": "zh-HK",
        },
    )

    assert result["outcome"] == "unavailable"
    assert result["effects"]["provider_requests"] == 0
    assert result["effects"]["transmitted_data_classes"] == []
