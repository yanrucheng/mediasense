"""Accepted exchange semantics, independent of model execution."""

from copy import deepcopy
import json
from pathlib import Path
import pytest
from jsonschema import Draft202012Validator, ValidationError
from mediasense.precheck._sensitivity_values import validate_observation

ROOT = Path(__file__).parents[1]
PACKET = json.loads(
    (
        ROOT
        / "openspec/changes/extend-local-sensitivity-observations/handoff.examples.json"
    ).read_text()
)
TOOL = json.loads(
    (ROOT / "docs/spec/contract/precheck-read/precheck-read.tool.json").read_text()
)
VALIDATOR = Draft202012Validator(
    {"$defs": TOOL["outputSchema"]["$defs"], "$ref": "#/$defs/observation"}
)
OBS = [o for c in PACKET["examples"] for o in c.get("observations", [])]


@pytest.mark.parametrize("observation", OBS)
def test_accepted_handoff(observation):
    VALIDATOR.validate(observation)
    validate_observation(observation)


@pytest.mark.parametrize(
    "change",
    ["missing_class", "sum", "cumulative", "unknown_kind", "box", "duplicate_kind"],
)
def test_contradictory_exchange_rejected(change):
    observations = deepcopy(OBS)
    classification = next(
        o for o in observations if "classification_distribution" in o.get("value", {})
    )
    region = next(o for o in observations if "region_detections" in o.get("value", {}))
    target = classification
    if change == "missing_class":
        del target["value"]["classification_distribution"]["probabilities"]["low"]
    elif change == "sum":
        target["value"]["classification_distribution"]["probabilities"]["low"] = 0.99
    elif change == "cumulative":
        target["value"]["cumulative_probabilities"]["high"] = 0.9
    elif change == "unknown_kind":
        target["value"]["logits"] = [1, 2]
    elif change == "duplicate_kind":
        target["provenance"]["definitions"]["declared_properties"] *= 2
    else:
        target = region
        target["value"]["region_detections"]["instances"][0]["box_xyxy"][2] = 999999
    with pytest.raises((ValueError, ValidationError)):
        VALIDATOR.validate(target)
        validate_observation(target)
