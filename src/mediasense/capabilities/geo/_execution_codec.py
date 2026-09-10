"""Private lossless codec for journaled provider executions."""

from .model import (
    GeoCandidate,
    GeoComponentResult,
    GeoCoordinate,
    GeoProviderAttempt,
)
from .protocol import GeoProviderExecution


def encode(execution: GeoProviderExecution) -> dict:
    return {
        "components": [c.value() for c in execution.components],
        "attempts": [a.value() for a in execution.attempts],
    }


def component(value: dict) -> GeoComponentResult:
    candidates = []
    for raw in value["candidates"]:
        candidate = dict(raw)
        candidate["components"] = tuple(candidate.get("components", {}).items())
        if candidate.get("coordinate") is not None:
            candidate["coordinate"] = GeoCoordinate(**candidate["coordinate"])
        candidates.append(GeoCandidate(**candidate))
    return GeoComponentResult(
        value["operation"],
        value["status"],
        tuple(value["subject_refs"]),
        GeoCoordinate(**value["coordinate"]),
        tuple(candidates),
        tuple(value.get("qualifications", ())),
        value.get("observed_at"),
    )


def attempt(value: dict) -> GeoProviderAttempt:
    raw = dict(value)
    raw["input_coordinate"] = GeoCoordinate(**raw["input_coordinate"])
    raw["provider_coordinate"] = (
        GeoCoordinate(**raw["provider_coordinate"])
        if raw["provider_coordinate"] is not None
        else None
    )
    return GeoProviderAttempt(**raw)


def decode(value: dict) -> GeoProviderExecution:
    components = tuple(component(c) for c in value["components"])
    attempts = tuple(attempt(a) for a in value["attempts"])
    return GeoProviderExecution(
        components[0], attempts[0], components[1:], attempts[1:]
    )
