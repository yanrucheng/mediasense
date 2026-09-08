"""Metric repair must identify the actual sealed Result, never rerun a stage."""

import hashlib
import importlib.util
import json
from pathlib import Path
import sqlite3

import pytest

PATH = (
    Path(__file__).parents[1] / "eval/sessions/260908-1329-precheck-corrections/run.py"
)
spec = importlib.util.spec_from_file_location("eval_replay", PATH)
replay = importlib.util.module_from_spec(spec)
spec.loader.exec_module(replay)


def test_repairs_only_references_and_rejects_corrupt_sealed_content(tmp_path):
    database = tmp_path / "workspace/precheck/work.sqlite3"
    database.parent.mkdir(parents=True)
    sealed = database.parent / "sealed.json"
    ref = "precheck-result:" + "a" * 64
    raw = json.dumps({"result": {"ref": ref}}).encode()
    sealed.write_bytes(raw)
    with sqlite3.connect(database) as db:
        db.executescript("""CREATE TABLE precheck_runs (run_ref TEXT, state TEXT, published_result_json TEXT);
            CREATE TABLE sealed_results (result_ref TEXT, relative_path TEXT, digest_algorithm TEXT, digest TEXT, size_bytes INTEGER);""")
        db.execute(
            "INSERT INTO precheck_runs VALUES (?, ?, ?)",
            ("run:completed", "completed", json.dumps({"result_ref": ref})),
        )
        db.execute(
            "INSERT INTO precheck_runs VALUES (?, ?, ?)", ("run:failed", "failed", None)
        )
        db.execute(
            "INSERT INTO sealed_results VALUES (?, ?, ?, ?, ?)",
            (ref, "sealed.json", "sha256", hashlib.sha256(raw).hexdigest(), len(raw)),
        )
    metric = {
        "run_ref": "run:completed",
        "state": "completed",
        "public_result": None,
        "elapsed_seconds": 42,
        "embedding_executed": 9,
    }
    (tmp_path / "completed.json").write_text(json.dumps(metric))
    (tmp_path / "failed.json").write_text(
        json.dumps({"run_ref": "run:failed", "state": "failed"})
    )
    before = database.read_bytes()
    assert replay.repair_metric_references(tmp_path) == {
        "completed.json": ref,
        "failed.json": None,
    }
    updated = json.loads((tmp_path / "completed.json").read_text())
    assert updated["public_result"] == ref
    assert updated["elapsed_seconds"] == 42 and updated["embedding_executed"] == 9
    assert database.read_bytes() == before and sealed.read_bytes() == raw
    sealed.write_bytes(b"corrupt")
    with pytest.raises(ValueError, match="integrity"):
        replay.repair_metric_references(tmp_path)
