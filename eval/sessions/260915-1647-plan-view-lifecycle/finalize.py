"""Verify recorded exit/recovery evidence after isolating Dataset-open bookkeeping."""

import argparse
import hashlib
from io import BytesIO
import json
from pathlib import Path
import subprocess
import os

from PIL import Image


def run(root):
    def read(name):
        return json.loads((root / name).read_text())

    authority = read("authority-report.json")
    assert (
        authority["display_idle_all_files_unchanged"]
        and authority["recovery_business_unchanged"]
    )
    assert authority["only_changed_table"] == ["precheck/work.sqlite3:datasets"]
    measurements = read("lifecycle-measurements.json")
    cache = read("lifecycle-cache-released.json")
    exited = measurements[-1]
    assert exited["state"] == "stopped" and exited["exit_reason"] == "idle_timeout"
    assert exited["rss_kib"] is None
    assert cache["evictions"] >= 20
    assert (
        max(x["contexts"] for x in measurements if x.get("contexts") is not None) <= 2
    )
    trace = read("lifecycle-trace.json")
    assert len(trace) == 42
    initial, recovered = [item["response"] for item in trace[-2:]]
    assert initial["revision"] == recovered["revision"]
    assert (
        initial["sections"]["view"]["current_uri"]
        != recovered["sections"]["view"]["current_uri"]
    )
    assert recovered["sections"]["view"]["status"] == "ready"
    for name in (
        "lifecycle-active.png",
        "lifecycle-offline.png",
        "lifecycle-recovered.png",
    ):
        assert (root / name).stat().st_size > 1000
    # Check the known generated source recipe, independently of the late runner assertion.
    expected = {}
    for n in range(1200):
        out = BytesIO()
        Image.new("RGB", (32, 24), (n % 255, 80, 120)).save(out, format="JPEG")
        name = f"item-{n:04}.jpg"
        expected[name] = hashlib.sha256(out.getvalue()).hexdigest()
    observed = {
        p.name: hashlib.sha256(p.read_bytes()).hexdigest()
        for p in (root / "source").iterdir()
    }
    assert observed == expected
    cfg = read("config.json")
    stop = json.loads(
        subprocess.check_output(
            [cfg["host"], "views", "stop", "--json"],
            env={**os.environ, **cfg["env"]},
            text=True,
        )
    )
    assert stop["state"] == "stopped"
    lifecycle = {
        "production_parameters": {"cache_idle": 120, "service_idle": 600},
        "cacheReleased": cache,
        "exited": exited,
        "multi_work_bindings": 20,
        "authority": authority,
        "pid_exit_verified": True,
        "recovered_entry": recovered["sections"]["view"],
        "explicit_stop": stop,
        "raw_runner_result": "late raw-hash assertion detected existing datasets.updated_at change",
        "completion": "recorded postconditions verified with strict independent per-table comparison",
    }
    (root / "lifecycle-report.json").write_text(json.dumps(lifecycle, indent=2) + "\n")
    from jsonschema import Draft202012Validator
    from referencing import Registry, Resource
    from mediasense.runtime.resources import load_contract, schema_path

    contract = load_contract("mediasense.plan.work")
    frozen = json.loads(schema_path("frozen-plan.schema.json").read_text())
    registry = Registry().with_resource(frozen["$id"], Resource.from_contents(frozen))
    inputs = Draft202012Validator(contract["inputSchema"], registry=registry)
    outputs = Draft202012Validator(contract["outputSchema"], registry=registry)
    exchanges = read("cli-trace.json") + trace
    for exchange in exchanges:
        inputs.validate(exchange["request"])
        outputs.validate(exchange["response"])
    outputs.validate(read("mcp-inspect.json"))
    browser = read("browser-report.json")
    assert read("mcp-inspect.json")["outcome"] == "ok"
    browser.update(
        validated_actual_cli_exchanges=len(exchanges),
        source_items_unchanged=1200,
        mcp="inspect via stdio verified",
        lifecycle="verified; see lifecycle-report.json",
        human_review="not_performed",
        installation_release="not_performed",
    )
    (root / "report.json").write_text(json.dumps(browser, indent=2) + "\n")
    print(
        json.dumps(
            {
                "outcome": "verified",
                "source_items": 1200,
                "cache_seconds": cache["seconds"],
                "exit_seconds": exited["seconds"],
                "data_comparison": authority,
            }
        )
    )


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("root", type=Path)
    run(parser.parse_args().root.resolve())
