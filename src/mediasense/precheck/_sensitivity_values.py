"""Pure validation of retained sensitivity values; no inference dependencies."""

from collections.abc import Mapping
import math

KINDS = {"classification_distribution", "cumulative_probabilities", "region_detections"}


def probability(value):
    if (
        isinstance(value, bool)
        or not isinstance(value, (float, int))
        or not math.isfinite(value)
        or not 0 <= value <= 1
    ):
        raise ValueError("Sensitivity score must be a finite probability in [0,1]")


def validate_named_value(value, definitions, basis, dimensions=None):
    """Check mathematical meaning in addition to the closed exchange schema."""
    if not isinstance(value, Mapping) or not isinstance(definitions, Mapping):
        raise ValueError("Sensitivity requires a value and saved definitions")
    kinds = set(value) - {"detector_identity", "profile"}
    declared = definitions.get("declared_properties", [])
    labels = definitions.get("labels", [])
    if (
        not kinds
        or not kinds <= KINDS
        or kinds != set(declared)
        or len(declared) != len(set(declared))
        or not labels
        or len(labels) != len(set(labels))
        or not all(isinstance(x, str) and x for x in labels)
        or not definitions.get("taxonomy")
        or not definitions.get("meaning")
    ):
        raise ValueError("Sensitivity output does not match its declared information")
    distribution = value.get("classification_distribution")
    if distribution is not None:
        if set(distribution) != {"taxonomy", "score_semantics", "probabilities"}:
            raise ValueError("Classification contains undeclared information")
        probabilities = distribution["probabilities"]
        if (
            distribution["score_semantics"] != "categorical_probability"
            or distribution["taxonomy"] != definitions["taxonomy"]
            or set(probabilities) != set(labels)
        ):
            raise ValueError("Classification taxonomy or categories do not match")
        for score in probabilities.values():
            probability(score)
        if not math.isclose(sum(probabilities.values()), 1, abs_tol=1e-6, rel_tol=0):
            raise ValueError("Classification probabilities must sum to one")
    cumulative = value.get("cumulative_probabilities")
    if cumulative is not None:
        derivation = basis.get("cumulative_probabilities", {})
        events = derivation.get("events", {})
        if (
            distribution is None
            or derivation.get("operation") != "sum"
            or derivation.get("source_property") != "classification_distribution"
            or not events
            or set(events) != set(cumulative)
        ):
            raise ValueError("Cumulative probabilities require their exact sum basis")
        for event, categories in events.items():
            if (
                not categories
                or len(categories) != len(set(categories))
                or not set(categories) <= set(labels)
            ):
                raise ValueError("Invalid cumulative event categories")
            probability(cumulative[event])
            if not math.isclose(
                cumulative[event],
                sum(distribution["probabilities"][x] for x in categories),
                abs_tol=1e-6,
                rel_tol=0,
            ):
                raise ValueError("Cumulative probability contradicts its basis")
    regions = value.get("region_detections")
    if regions is not None:
        if set(regions) != {
            "taxonomy",
            "score_semantics",
            "coordinate_system",
            "input_dimensions",
            "instances",
        }:
            raise ValueError("Region value contains undeclared information")
        if (
            regions["taxonomy"] != definitions["taxonomy"]
            or regions["score_semantics"] != "model_detection_score"
            or regions["coordinate_system"] != "input_evidence_pixels_xyxy"
        ):
            raise ValueError("Invalid region meaning")
        size = regions["input_dimensions"]
        if set(size) != {"width", "height"} or any(
            type(n) is not int or n < 1 for n in size.values()
        ):
            raise ValueError("Invalid input dimensions")
        if dimensions is not None and size != dimensions:
            raise ValueError("Region dimensions disagree with actual input Evidence")
        for instance in regions["instances"]:
            if (
                set(instance) != {"label", "score", "box_xyxy"}
                or instance["label"] not in labels
            ):
                raise ValueError("Invalid region instance or taxonomy label")
            probability(instance["score"])
            box = instance["box_xyxy"]
            if len(box) != 4 or any(type(n) is not int for n in box):
                raise ValueError("Native region coordinates must be four integers")
            x1, y1, x2, y2 = box
            if not (0 <= x1 < x2 <= size["width"] and 0 <= y1 < y2 <= size["height"]):
                raise ValueError("Region coordinates outside actual input or zero area")
    profile = value["profile"]
    if profile == "freepik-ordinal448-mps-fp32-v1":
        expected = {
            "at_least_low": ["low", "medium", "high"],
            "at_least_medium": ["medium", "high"],
            "high": ["high"],
        }
        if (
            kinds != {"classification_distribution", "cumulative_probabilities"}
            or labels != ["neutral", "low", "medium", "high"]
            or basis["cumulative_probabilities"]["events"] != expected
        ):
            raise ValueError(
                "Freepik requires all native classes and cumulative events"
            )
    if profile == "nudenet640-native-cpu-fp32-v1":
        from ._sensitivity_profiles import LABELS_640

        postprocessing = basis.get("postprocessing", {})
        if (
            kinds != {"region_detections"}
            or labels != LABELS_640
            or any(
                postprocessing.get(k) != v
                for k, v in {
                    "candidate_confidence": 0.2,
                    "nms_score_threshold": 0.25,
                    "nms_iou": 0.45,
                    "class_agnostic": True,
                }.items()
            )
        ):
            raise ValueError(
                "NudeNet 640 requires its full native taxonomy and postprocessing"
            )


def validate_observation(observation):
    value = observation.get("value", {})
    if (
        observation.get("name") != "content_sensitivity"
        or observation.get("status") != "available"
    ):
        return
    if "labels" in value:
        if value.get("profile") in {
            "freepik-ordinal448-mps-fp32-v1",
            "nudenet640-native-cpu-fp32-v1",
        }:
            raise ValueError(
                "Named-value profiles cannot masquerade as legacy label summaries"
            )
        for item in value["labels"]:
            for score, threshold, decision in (
                ("score", "threshold", "sensitive"),
                ("score", "mild_threshold", "mild_sensitive"),
            ):
                if (
                    threshold in item
                    and decision in item
                    and item[decision] != (item[score] >= item[threshold])
                ):
                    raise ValueError(
                        "Historical sensitivity comparison contradicts recorded values"
                    )
        return
    provenance = observation["provenance"]
    if any(value[k] != provenance[k] for k in ("detector_identity", "profile")):
        raise ValueError("Sensitivity provenance and value identities disagree")
    validate_named_value(value, provenance["definitions"], observation["basis"])


def validate_input_links(sources, evidence, derivations):
    """One pure source/input/dimension check shared by seal and retained Read."""
    edges = {}
    for origin, target in derivations:
        edges.setdefault(origin, []).append(target)
    resolved = {}

    for subject_ref, subject in (*sources.items(), *evidence.items()):
        for observation in subject.get("observations", ()):
            if observation["name"] != "content_sensitivity" or observation[
                "status"
            ] not in {"available", "failed"}:
                continue
            input_ref = observation["provenance"]["input_evidence_ref"]
            if input_ref not in evidence:
                raise ValueError("Sensitivity input Evidence is outside this Result")
            if subject_ref not in sources or subject_ref not in _input_source_refs(
                input_ref, set(), sources, evidence, edges, resolved
            ):
                raise ValueError(
                    "Sensitivity input does not derive from its Source Item"
                )
            regions = observation.get("value", {}).get("region_detections")
            if regions is not None:
                dimensions = [
                    o["value"]
                    for o in evidence[input_ref].get("observations", ())
                    if o["name"] in {"pixel_dimensions", "video_frame"}
                    and o["status"] == "available"
                ]
                if not dimensions or any(
                    {k: d[k] for k in ("width", "height")}
                    != regions["input_dimensions"]
                    for d in dimensions
                ):
                    raise ValueError(
                        "Sensitivity region dimensions disagree with actual input Evidence"
                    )


def _input_source_refs(ref, visiting, sources, evidence, edges, resolved):
    # Explicit call-local maps avoid a recursive closure keeping a complete
    # sealed graph alive after validation. The memo remains invocation-local.
    if ref in sources:
        return {ref}
    if ref not in evidence:
        raise ValueError("Sensitivity input lineage leaves this Result")
    if ref in visiting:
        raise ValueError("Sensitivity input lineage is cyclic")
    if ref not in resolved:
        found = set()
        access = evidence[ref].get("access", {})
        if access.get("kind") == "source_item":
            source = access.get("source_item_ref")
            if source not in sources:
                raise ValueError("Sensitivity input source is outside this Result")
            found.add(source)
        for target in edges.get(ref, ()):
            found.update(_input_source_refs(
                target, visiting | {ref}, sources, evidence, edges, resolved
            ))
        resolved[ref] = found
    return resolved[ref]
