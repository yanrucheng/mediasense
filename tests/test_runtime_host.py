from __future__ import annotations

from pathlib import Path

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
