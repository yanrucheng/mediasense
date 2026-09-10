"""Hard process termination at Geo durability boundaries; no network or models."""

from datetime import datetime, timezone
from pathlib import Path
import subprocess
import sys
import time

import pytest

from mediasense.capabilities.geo import (
    GeoAuthorization,
    GeoCapability,
    GeoComponentResult,
    GeoComponentStatus,
    GeoCoordinate,
    GeoOperation,
    GeoOperationJournal,
    GeoProviderAttempt,
    GeoProviderCapabilities,
    GeoProviderExecution,
    GeoQueryTool,
    GeoRequest,
    GeoSubject,
    MapDatum,
    OrderedGeoRoutingPolicy,
)


def stop_at(root):
    (root / "ready").write_text("owned")
    while True:
        time.sleep(0.1)


def tool(root, stage=None):
    class Provider:
        capabilities = GeoProviderCapabilities(
            "synthetic",
            (GeoOperation.REVERSE_GEOCODE,),
            MapDatum.WGS84,
            max_billable_units_per_operation=1,
            repeatable_queries=True,
        )

        def execute(self, operation, coordinate, **kwargs):
            with (root / "calls").open("a") as log:
                log.write("sent\n")
            if stage == "after_send":
                stop_at(root)
            return GeoProviderExecution(
                GeoComponentResult(
                    operation, GeoComponentStatus.NO_RESULT, (), coordinate
                ),
                GeoProviderAttempt(
                    "synthetic",
                    operation,
                    GeoComponentStatus.NO_RESULT,
                    coordinate,
                    coordinate,
                    1,
                    1,
                ),
            )

    provider = Provider()
    geo = GeoQueryTool(
        GeoCapability({"synthetic": provider}, OrderedGeoRoutingPolicy(("synthetic",))),
        GeoOperationJournal(root / "journal.sqlite3"),
    )
    if stage == "before_request":
        geo._execute = lambda *args, **kwargs: stop_at(root)
    if stage == "before_record":
        geo.journal.record_execution = lambda *args, **kwargs: stop_at(root)
    if stage == "before_complete":
        geo.journal.complete = lambda *args, **kwargs: stop_at(root)
    return geo


def request_and_authority(geo):
    value = GeoRequest(
        GeoOperation.REVERSE_GEOCODE,
        (GeoSubject("test", GeoCoordinate(35.0, 139.0)),),
        "en",
    )
    auth = GeoAuthorization(
        "human:synthetic",
        geo.capability.fingerprint(value),
        datetime(2026, 9, 10, tzinfo=timezone.utc),
        geo.capability.proposed_envelope(value),
    )
    return {"request_id": "request:hard-stop", **value.value()}, auth


def terminated_child(root, stage, *arguments):
    child = subprocess.Popen(
        [
            sys.executable,
            str(Path(__file__).resolve()),
            "--child",
            str(root),
            stage,
            *arguments,
        ],
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )
    try:
        until = time.monotonic() + 20
        while not (root / "ready").exists():
            if child.poll() is not None:
                raise AssertionError(child.communicate())
            if time.monotonic() > until:
                raise AssertionError("child did not reach the checkpoint")
            time.sleep(0.01)
        return child
    except BaseException:
        child.kill()
        child.wait(timeout=5)
        raise


@pytest.mark.parametrize(
    "stage", ["before_request", "after_send", "before_record", "before_complete"]
)
def test_hard_kill_retains_effect_knowledge_and_replay_is_effect_free(tmp_path, stage):
    child = terminated_child(tmp_path, stage)
    geo = tool(tmp_path)
    request, auth = request_and_authority(geo)
    try:
        assert geo.handle(request)["error"]["code"] == "execution_in_progress"
    finally:
        child.kill()
        child.wait(timeout=5)
    result = geo.handle(request)
    calls = (
        (tmp_path / "calls").read_text().splitlines()
        if (tmp_path / "calls").exists()
        else []
    )
    assert len(calls) == (0 if stage == "before_request" else 1)
    assert geo.handle(request) == result
    if stage == "before_request":
        assert result["effects"]["provider_requests"] == 0
        assert result["components"][0]["status"] == "not_requested"
    elif stage == "before_complete":
        assert result["effects"]["provider_requests"] == 1
        assert result["components"][0]["status"] == "no_result"
    else:
        assert result["effects"]["provider_requests"] is None
        assert result["effects"]["provider_requests_upper_bound"] == 1
        assert result["effects"]["billable_units"] is None
        assert result["attempts"][0]["request_count_kind"] == "reserved_upper_bound"


def projection_producer(root, *, child=False):
    from mediasense.geo import GoogleMapsReverseGeocoder
    from mediasense.precheck import ReverseGeocodeProducer, PrecheckRunTool

    class Transport:
        def get_json(self, *args, **kwargs):
            with (root / "calls").open("a") as out:
                out.write("GET\n")
            return {
                "status": "OK",
                "results": [{"formatted_address": "Saved", "address_components": []}],
            }

        def post_json(self, *args, **kwargs):
            with (root / "calls").open("a") as out:
                out.write("POST\n")
            return {"places": [{"displayName": {"text": "Saved place"}}]}

    provider = GoogleMapsReverseGeocoder(
        "synthetic", transport=Transport(), minimum_interval=0
    )
    geo = GeoQueryTool(
        GeoCapability(
            {"google_maps": provider}, OrderedGeoRoutingPolicy(("google_maps",))
        ),
        GeoOperationJournal(root / "journal.sqlite3"),
    )
    producer = ReverseGeocodeProducer(
        root / "work.sqlite3", PrecheckRunTool(root / "work.sqlite3"), geo
    )
    if child:
        producer._persist_response = lambda *args, **kwargs: stop_at(root)
    return producer


def test_hard_kill_during_work_projection_reclaims_only_owned_projection(tmp_path):
    from test_geocode import _closed_run, _coordinate_work, _public_run, _authorize
    from mediasense.precheck import AccountingStore

    database = tmp_path / "work.sqlite3"
    accounting = AccountingStore(database)
    accounting.register_dataset("dataset-a")
    run_id = _closed_run(tmp_path, database, accounting, ("a.jpg",))
    metadata = _coordinate_work(
        database, run_id, "a.jpg", latitude=35.0, longitude=139.0
    )
    producer = projection_producer(tmp_path)
    run_ref = _public_run(producer.run_tool, "request:projection-kill")
    assert (
        producer.produce(run_ref, run_id, [metadata.work_id]).status
        == "confirmation_required"
    )
    _authorize(producer.run_tool, run_ref)
    child = terminated_child(tmp_path, "projection", run_ref, run_id, metadata.work_id)
    child.kill()
    child.wait(timeout=5)
    assert (tmp_path / "calls").read_text().splitlines() == ["GET", "POST"]
    recovered = projection_producer(tmp_path).produce(
        run_ref, run_id, [metadata.work_id]
    )
    assert recovered.status == "completed"
    assert (tmp_path / "calls").read_text().splitlines() == ["GET", "POST"]
    assert recovered.outcomes[0].work.output["result"]["status"] == "success"


if __name__ == "__main__":
    root = Path(sys.argv[2])
    stage = sys.argv[3]
    if stage == "projection":
        projection_producer(root, child=True).produce(
            sys.argv[4], sys.argv[5], [sys.argv[6]]
        )
    else:
        geo = tool(root, stage)
        request, authority = request_and_authority(geo)
        geo.handle(request, authorization=authority)
