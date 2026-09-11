"""Contract checks and pure profile comparison; no producer/model/provider runs."""

from copy import deepcopy
from dataclasses import asdict
from datetime import datetime
import hashlib
import json
from pathlib import Path
import re

from jsonschema import Draft202012Validator, FormatChecker
import pytest


ROOT = Path(__file__).parents[1]
SPEC = ROOT / "docs/spec/contract/precheck-read"
TOOL = json.loads((SPEC / "precheck-read.tool.json").read_text())
PACKET = json.loads((SPEC / "examples.json").read_text())
LOCAL_READ_FAILURES = {"evidence_unavailable", "response_item_too_large"}
REQUIRED_MEMBER_SUMMARIES = {"capture_time_range", "media_type_counts"}


def validator(action=None):
    schema = (
        TOOL["inputSchema"]
        if action is None
        else {"$defs": TOOL["outputSchema"]["$defs"], **TOOL["responseSchemas"][action]}
    )
    return Draft202012Validator(schema, format_checker=FormatChecker())


def identity(value):
    return (
        "sha256:"
        + hashlib.sha256(
            json.dumps(
                value, ensure_ascii=False, sort_keys=True, separators=(",", ":")
            ).encode()
        ).hexdigest()
    )


@pytest.mark.parametrize("name", ["video_frame", "video_contact_sheet"])
def test_video_observed_position_is_optional_but_cannot_be_negative_or_null(name):
    frame = {"sample_time_seconds": 12.3123, "decoded_time_seconds": 8.2082}
    value = ({**frame, "width": 320, "height": 180} if name == "video_frame" else
             {"columns": 1, "width": 320, "height": 180,
              "frames": [{"evidence_ref": "evidence:frame", **frame}]})
    observation = {"name": name, "status": "available", "value": value,
                   "basis": {"producer": "local-decoder", "position": "presentation_timestamp"}}
    check = Draft202012Validator({"$defs": TOOL["outputSchema"]["$defs"], "$ref": "#/$defs/observation"})
    check.validate(observation)
    position = value if name == "video_frame" else value["frames"][0]
    for invalid in (-0.001, None):
        position["decoded_time_seconds"] = invalid
        assert not check.is_valid(observation)
    del position["decoded_time_seconds"]
    check.validate(observation)  # historical requested targets do not become actual PTS


def walk(value):
    if isinstance(value, dict):
        yield value
        for child in value.values():
            yield from walk(child)
    elif isinstance(value, list):
        for child in value:
            yield from walk(child)


def check_observations(observations):
    """Check only declared Observations; their nested values remain extension data."""
    seen = set()
    for observation in observations:
        assert (observation["status"] == "available") == ("value" in observation), (
            "Observation status/value mismatch"
        )
        name = observation["name"]
        key = (name,)
        if name == "content_sensitivity":
            provenance = observation.get("provenance", {})
            value = observation.get("value", {})
            key = (
                name,
                value.get("detector_identity", provenance.get("detector_identity")),
                provenance.get("input_evidence_ref"),
            )
            if value.get("profile") in {
                "falconsai-nsfw-c90-thresholds-v1",
                "nudenet-body-exposure-c90-thresholds-v1",
            }:
                for label in value["labels"]:
                    assert {
                        "threshold",
                        "mild_threshold",
                        "sensitive",
                        "mild_sensitive",
                    } <= label.keys(), "recorded V1 classification fields are required"
                    assert label["sensitive"] == (label["score"] >= label["threshold"])
                    assert label["mild_sensitive"] == (
                        label["score"] >= label["mild_threshold"]
                    )
        assert key not in seen, f"duplicate observation: {key}"
        seen.add(key)


def check_semantics(request, response):
    """Public cross-field assertions; runtime source/lineage proofs are checked by delivery tests."""
    try:
        encoded = json.dumps(
            response, ensure_ascii=False, separators=(",", ":"), allow_nan=False
        )
    except ValueError as error:
        raise AssertionError("response must contain finite JSON numbers") from error
    assert len(encoded.encode("utf-8")) <= 524288
    if "error" in response:
        assert set(response) == {"error"}
        if request["action"] == "review":
            error = response["error"]
            assert error["code"] != "evidence_unavailable", "use an item failure record"
            if error["code"] == "response_item_too_large":
                assert "evidence_ref" not in error, "use an item failure record"
        return
    for value in walk(response):
        assert not {
            "work_id",
            "input_work_id",
            "frame_work_ids",
            "cache_key",
            "row_id",
        }.intersection(value)
    # Only declared Observation containers, never arbitrary inline/attribute data.
    for item in response.get("items", []):
        containers = [item, item.get("included", {})]
        containers.extend(item.get("source_items", []))
        containers.append(item.get("included", {}).get("anchor_evidence", {}))
        containers.append(item.get("represents", {}))
        for container in containers:
            if "observations" in container:
                check_observations(container["observations"])
    if "result" in response:
        assert request["result_ref"] == response["result"]["ref"]
    if "accounting" in response:
        account = response["accounting"]
        assert account["total"] == sum(account["routes"].values())
        assert account["total"] == sum(x["count"] for x in account["scope_condition"])
        frontier = account["frontier"]
        assert (
            frontier["coverage_memberships"]
            >= frontier["represented_unique_source_items"]
        )
        assert frontier["represented_unique_source_items"] == (
            account["routes"]["frontier_only"]
            + account["routes"]["frontier_and_exception"]
        )
    if request["action"] == "review":
        assert len({x["evidence_ref"] for x in response["items"]}) == len(
            response["items"]
        )
        for item in response["items"]:
            if "error" in item:
                assert set(item) == {"evidence_ref", "error"}
                assert item["error"]["code"] in LOCAL_READ_FAILURES
                continue
            rep = item["represents"]
            assert rep["source_set"]["origin"] == item["evidence_ref"]
            assert rep["source_count"] == sum(
                x["count"] for x in rep["scope_condition"]
            )
            refs = [s["source_item_ref"] for s in item["source_items"]]
            assert refs == sorted(set(refs))
            for role_refs in item.get("roles", {}).values():
                assert item["evidence_ref"] not in role_refs
            assert REQUIRED_MEMBER_SUMMARIES <= {
                o["name"] for o in rep["observations"]
            }, "required member summaries missing"
            for o in rep["observations"]:
                if o["name"] not in REQUIRED_MEMBER_SUMMARIES:
                    continue
                value = o.get("value", o.get("basis", {}))
                counts = value.get("status_counts")
                assert counts is not None, "member summary coverage is required"
                assert sum(counts.values()) == rep["source_count"]
                if o["name"] == "capture_time_range" and o["status"] == "available":
                    assert datetime.fromisoformat(
                        value["earliest"]
                    ) <= datetime.fromisoformat(value["latest"])
                if o["name"] == "media_type_counts" and o["status"] == "available":
                    assert sum(x["count"] for x in value["values"]) == counts.get(
                        "available", 0
                    )
    if "resolution" in response:
        members = [m["source_item_ref"] for m in response["members"]]
        assert members == sorted(set(members))
        assert response["resolution"]["source_set_identity"] == identity(
            request["source_set"]
        )
        if response["page"]["next_cursor"] is None and response["page"]["total"] == len(
            members
        ):
            assert response["resolution"]["membership_identity"] == identity(
                {
                    "result_ref": request["result_ref"],
                    "source_set": request["source_set"],
                    "members": members,
                }
            )
    for group in response.get("coordinate_groups", []):
        for counts in group["components"].values():
            assert sum(counts.values()) == group["member_count"]
    page = response.get("page")
    if page:
        items = response.get(
            "items", response.get("members", response.get("coordinate_groups", []))
        )
        assert len(items) <= page["total"]
        if "limit" in request.get("page", {}):
            assert len(items) <= request["page"]["limit"]
        if page["next_cursor"] is not None:
            assert items, "non-terminal pages must advance"
            assert page["next_cursor"] != request.get("page", {}).get("cursor")
        if page.get("stop_reason"):
            assert page["next_cursor"] is not None
        if page["next_cursor"] is None and not request.get("page", {}).get("cursor"):
            assert len(items) == page["total"]


def check_review_page_series(exchanges, expected_refs):
    """Check complete enumeration, including failures, against the synthetic Result."""
    first = exchanges[0]
    binding = {k: v for k, v in first["request"].items() if k != "page"}
    cursor = None
    cursors = set()
    refs = []
    for index, exchange in enumerate(exchanges):
        request, response = exchange["request"], exchange["response"]
        assert {k: v for k, v in request.items() if k != "page"} == binding
        assert request["page"]["limit"] == first["request"]["page"]["limit"]
        assert request["page"].get("cursor") == cursor
        validator().validate(request)
        validator("review").validate(response)
        check_semantics(request, response)
        assert "error" not in response, "local item failures must not abort the series"
        assert response["result"] == first["response"]["result"]
        assert response["accounting"] == first["response"]["accounting"]
        assert response["page"]["total"] == len(expected_refs)
        refs.extend(item["evidence_ref"] for item in response["items"])
        cursor = response["page"]["next_cursor"]
        if index < len(exchanges) - 1:
            assert cursor is not None and cursor not in cursors
            cursors.add(cursor)
    assert cursor is None
    assert refs == expected_refs, "every selected Evidence needs exactly one outcome"
    assert len(refs) == len(set(refs))


@pytest.mark.parametrize("exchange", PACKET["exchanges"], ids=lambda x: x["name"])
def test_action_bound_exchange(exchange):
    validator().validate(exchange["request"])
    validator(exchange["request"]["action"]).validate(exchange["response"])
    check_semantics(exchange["request"], exchange["response"])


@pytest.mark.parametrize("case", PACKET["negative"], ids=lambda x: x["name"])
def test_schema_rejects_invalid_exchange(case):
    selected = validator() if case["side"] == "input" else validator(case["action"])
    assert not selected.is_valid(case["value"])


@pytest.mark.parametrize("case", PACKET["semantic_negative"], ids=lambda x: x["name"])
def test_semantic_contradiction_is_not_hidden_by_valid_shape(case):
    validator(case["request"]["action"]).validate(case["response"])
    with pytest.raises(AssertionError):
        check_semantics(case["request"], case["response"])


def strip_jsonc(source):
    """Remove // comments without treating slashes inside strings as comments."""
    out = []
    i = 0
    quoted = False
    while i < len(source):
        char = source[i]
        if quoted:
            out.append(char)
            if char == "\\" and i + 1 < len(source):
                i += 1
                out.append(source[i])
            elif char == '"':
                quoted = False
            i += 1
            continue
        if char == '"':
            quoted = True
        if source[i : i + 2] == "//":
            end = source.find("\n", i)
            i = len(source) if end < 0 else end
            continue
        out.append(char)
        i += 1
    return "".join(out)


def test_commented_human_example_matches_machine_contract():
    blocks = re.findall(r"```jsonc\n(.*?)\n```", (SPEC / "index.md").read_text(), re.S)
    request, selected_request, response, failure = [
        json.loads(strip_jsonc(x)) for x in blocks
    ]
    validator().validate(request)
    validator().validate(selected_request)
    validator("review").validate(response)
    check_semantics(request, response)
    Draft202012Validator(
        {
            "$defs": TOOL["outputSchema"]["$defs"],
            "$ref": "#/$defs/review_item_failure",
        }
    ).validate(failure)


def test_unknown_attribute_does_not_require_new_model_entity():
    response = deepcopy(PACKET["exchanges"][0]["response"])
    response["items"][0]["source_items"][0]["observations"].append(
        {
            "name": "future_optical_signal",
            "status": "available",
            "value": {"unit": "example", "reading": 2},
        }
    )
    validator("review").validate(response)
    check_semantics(PACKET["exchanges"][0]["request"], response)


def test_nested_extension_data_is_not_reinterpreted_as_observations():
    exchange = deepcopy(PACKET["exchanges"][0])
    exchange["response"]["items"][0]["source_items"][0]["observations"].append(
        {
            "name": "future_menu_analysis",
            "status": "available",
            "value": {
                # These fields belong to the extension's own data format.
                "name": "menu_sections",
                "status": "available",
                "observations": [
                    {"name": "cuisine", "status": "candidate", "value": "Cantonese"},
                    {"name": "cuisine", "status": "candidate", "value": "Western"},
                ],
            },
        }
    )
    validator("review").validate(exchange["response"])
    check_semantics(exchange["request"], exchange["response"])


@pytest.mark.parametrize(
    "observation",
    [
        {"name": "future_signal", "status": "available"},
        {"name": "future_signal", "status": "missing", "value": "unexpected"},
    ],
    ids=["available-without-value", "missing-with-value"],
)
def test_invalid_observation_in_declared_container_is_still_rejected(observation):
    exchange = deepcopy(PACKET["exchanges"][0])
    exchange["response"]["items"][0]["source_items"][0]["observations"].append(
        observation
    )
    assert not validator("review").is_valid(exchange["response"])
    with pytest.raises(AssertionError, match="Observation status/value mismatch"):
        check_semantics(exchange["request"], exchange["response"])


def test_all_actions_and_image_path_boundary_are_covered():
    assert {e["request"]["action"] for e in PACKET["exchanges"]} == {
        "review",
        "expand",
        "resolve",
        "geo_summary",
    }
    for e in PACKET["exchanges"]:
        if "error" not in e["response"]:
            assert (
                "content" not in e["response"]
                and "structuredContent" not in e["response"]
            )
    definitions = TOOL["outputSchema"]["$defs"]
    assert definitions["page"]["required"] == ["total", "next_cursor"]
    assert "source_content_verification" in definitions["resolved_member"]["required"]


def test_examples_preserve_own_source_versus_represented_members():
    cases = {x["name"]: x for x in PACKET["exchanges"]}
    photo = cases["photo-one-of-twenty"]["response"]["items"][0]
    assert [x["source_item_ref"] for x in photo["source_items"]] == ["source-item:R"]
    assert photo["represents"]["source_count"] == 20
    own_time = next(
        x["value"]
        for x in photo["source_items"][0]["observations"]
        if x["name"] == "capture_time"
    )
    span = next(
        x["value"]
        for x in photo["represents"]["observations"]
        if x["name"] == "capture_time_range"
    )
    assert span["earliest"] < own_time < span["latest"]
    highres = cases["selected-highres"]["response"]["items"][0]
    assert highres["represents"]["source_count"] == 1
    composite = cases["multi-source-composite"]["response"]["items"][0]
    assert [x["source_item_ref"] for x in composite["source_items"]] == [
        "source-item:R",
        "source-item:S",
    ]
    sheet = cases["video-sheet-through-three-frames"]["response"]["items"][0]
    assert [x["source_item_ref"] for x in sheet["source_items"]] == ["source-item:V"]
    frames = sheet["observations"][0]["value"]["frames"]
    assert [x["sample_time_seconds"] for x in frames] == [0, 10, 20]
    assert len({x["evidence_ref"] for x in frames}) == 3


@pytest.mark.parametrize("series", PACKET["page_series"], ids=lambda x: x["name"])
def test_complete_review_page_series_keeps_every_outcome(series):
    cases = {x["name"]: x for x in PACKET["exchanges"]}
    check_review_page_series(
        [cases[name] for name in series["exchanges"]], series["expected_evidence_refs"]
    )


@pytest.mark.parametrize("defect", ["silent-skip", "repeat", "stuck", "early-end"])
def test_page_series_rejects_lost_or_repeated_outcomes(defect):
    cases = {x["name"]: x for x in PACKET["exchanges"]}
    pages = [deepcopy(cases[f"review-unavailable-page-{i}"]) for i in range(1, 4)]
    middle = pages[1]["response"]
    if defect == "silent-skip":
        middle["items"] = []
    elif defect == "repeat":
        middle["items"][0]["evidence_ref"] = "evidence:E1"
    elif defect == "stuck":
        middle["page"]["next_cursor"] = pages[1]["request"]["page"]["cursor"]
    else:
        middle["page"]["next_cursor"] = None
    validator("review").validate(middle)
    with pytest.raises(AssertionError):
        check_review_page_series(pages, ["evidence:E1", "evidence:E2", "evidence:E3"])


def test_mixed_page_counts_failure_as_one_slot_without_claiming_delivery():
    cases = {x["name"]: x for x in PACKET["exchanges"]}
    exchange = deepcopy(cases["review-unavailable-page-1"])
    exchange["request"]["page"]["limit"] = 3
    exchange["response"]["items"] = [
        deepcopy(cases[f"review-unavailable-page-{i}"]["response"]["items"][0])
        for i in range(1, 4)
    ]
    exchange["response"]["page"]["next_cursor"] = None
    check_review_page_series([exchange], ["evidence:E1", "evidence:E2", "evidence:E3"])
    items = exchange["response"]["items"]
    assert sum("access" in item for item in items) == 2
    assert sum("error" in item for item in items) == 1


@pytest.mark.parametrize("scope", ["evidence", "source", "relationship", "expand"])
def test_observation_uniqueness_applies_to_each_subject(scope):
    cases = {x["name"]: x for x in PACKET["exchanges"]}
    name = (
        "expand-source-own-observations" if scope == "expand" else "photo-one-of-twenty"
    )
    exchange = deepcopy(cases[name])
    item = exchange["response"]["items"][0]
    if scope == "source":
        observations = item["source_items"][0]["observations"]
    elif scope == "relationship":
        observations = item["represents"]["observations"]
    elif scope == "expand":
        observations = item["included"]["observations"]
    else:
        observations = item["observations"]
    observations.append(deepcopy(observations[0]))
    validator(exchange["request"]["action"]).validate(exchange["response"])
    with pytest.raises(AssertionError, match="duplicate observation"):
        check_semantics(exchange["request"], exchange["response"])


def test_sensitivity_uniqueness_uses_detector_and_input_instead_of_name_alone():
    cases = {x["name"]: x for x in PACKET["exchanges"]}
    exchange = deepcopy(cases["one-detector-success-one-failed"])
    observations = exchange["response"]["items"][0]["source_items"][0]["observations"]
    success = next(
        o
        for o in observations
        if o["name"] == "content_sensitivity" and o["status"] == "available"
    )
    another_input = deepcopy(success)
    another_input["provenance"]["input_evidence_ref"] = "evidence:another-frame"
    observations.append(another_input)
    validator("review").validate(exchange["response"])
    check_semantics(exchange["request"], exchange["response"])
    observations.append(deepcopy(success))
    with pytest.raises(AssertionError, match="duplicate observation"):
        check_semantics(exchange["request"], exchange["response"])


@pytest.mark.parametrize(
    "profile_name", ["NSFW_BINARY_PROFILE_V1", "NUDENET_BODY_EXPOSURE_PROFILE_V1"]
)
def test_existing_profile_classifications_fit_contract_without_value_loss(profile_name):
    # Pure numerical comparison only: no detector/producer is constructed or run.
    from mediasense.precheck import sensitivity

    profile = getattr(sensitivity, profile_name)
    labels = [
        asdict(x)
        for x in sensitivity.classify_detections(
            tuple(sensitivity.Detection(t.label, 0.999) for t in profile.thresholds),
            profile,
        )
    ]
    ignored = [label for label in labels if label["threshold"] > 1]
    assert ignored
    assert all(
        label["threshold"] == 99 and label["mild_threshold"] == 33 for label in ignored
    )
    assert all(
        not label["sensitive"] and not label["mild_sensitive"] for label in ignored
    )
    exchange = deepcopy(
        next(
            x
            for x in PACKET["exchanges"]
            if x["name"] == "nsfw-normal-cutoff-above-score-range"
        )
    )
    value = exchange["response"]["items"][0]["source_items"][0]["observations"][-1][
        "value"
    ]
    value.update(profile=profile.name, labels=labels)
    validator("review").validate(exchange["response"])
    check_semantics(exchange["request"], exchange["response"])


@pytest.mark.parametrize("number", [float("inf"), float("nan")])
def test_thresholds_remain_finite_json_numbers(number):
    exchange = deepcopy(
        next(
            x
            for x in PACKET["exchanges"]
            if x["name"] == "nsfw-normal-cutoff-above-score-range"
        )
    )
    label = exchange["response"]["items"][0]["source_items"][0]["observations"][-1][
        "value"
    ]["labels"][0]
    label["threshold"] = number
    with pytest.raises(AssertionError, match="finite JSON numbers"):
        check_semantics(exchange["request"], exchange["response"])
