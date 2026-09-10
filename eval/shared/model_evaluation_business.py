"""Thin evaluation binding to the installed MediaSense business algorithms."""

from dataclasses import asdict
from datetime import datetime
from pathlib import Path

from model_evaluation_inputs import digest, fingerprint


def business_code() -> dict:
    import mediasense.precheck

    root = Path(mediasense.precheck.__file__).parent
    files = {
        str(path.relative_to(root)): digest(path) for path in sorted(root.rglob("*.py"))
    }
    return {
        "package": "mediasense.precheck",
        "files": len(files),
        "sha256": fingerprint(files),
    }


def verify_business(config: dict) -> None:
    if business_code() != config["inputs"]["business_code"]:
        raise ValueError(
            "Installed business code changed; create a corresponding baseline recipe"
        )
    if (
        config["classification"]["algorithm"]
        != "mediasense_content_boundaries_with_anchor"
    ):
        raise ValueError("Unknown business classification algorithm")
    if not config["classification"]["profile"]["content_based_boundaries"]:
        raise ValueError("This business recipe requires content boundaries with anchor")
    if (
        config["inputs"]["compression_target"]
        != config["classification"]["profile"]["target_entries"]
    ):
        raise ValueError("Preparation and classification must use the same target")


def prepared_identity(prepared: dict) -> str:
    return fingerprint(
        {
            "recipe": prepared["recipe"],
            "source_fingerprint": prepared["source_fingerprint"],
            "business": prepared["business"],
            "inputs": [
                {
                    key: value
                    for key, value in row.items()
                    if key not in {"image_path", "error"}
                }
                for row in prepared["inputs"]
            ],
        }
    )


def comparison_identity(config: dict, prepared: dict) -> str:
    # A candidate's model/framework/preprocessing is deliberately not a business invariant.
    return fingerprint(
        {
            "inputs": prepared["input_fingerprint"],
            "classification": config["classification"],
            "binding_sha256": digest(Path(__file__)),
            "preparation_binding_sha256": digest(
                Path(__file__).with_name("model_evaluation_business_inputs.py")
            ),
        }
    )


def check_baseline(config: dict, prepared: dict) -> str:
    identity = comparison_identity(config, prepared)
    if config.get("baseline_ref"):
        import json

        baseline = json.loads(Path(config["baseline_ref"]).read_text())
        if baseline.get("classification_fingerprint") != identity:
            raise ValueError(
                "Baseline has different business inputs, algorithm or parameters; rebaseline first"
            )
    return identity


def classify(config: dict, prepared: dict, vectors: dict) -> dict:
    verify_business(config)
    from mediasense.precheck.compression import (
        AdaptiveCompressionProfile,
        CompressionPoint,
        build_adaptive_groups,
        select_embedding_representative,
    )

    expected = {row["id"] for row in prepared["inputs"] if row["state"] == "ready"}
    if set(vectors) != expected:
        raise ValueError(
            "Business classification requires exactly the accounted ready vectors"
        )
    by_source = {}
    for row in prepared["inputs"]:
        if row["id"] in vectors:
            by_source.setdefault(row["source"], []).append(row)
    selected = {}
    for source, rows in by_source.items():
        if rows[0]["kind"] == "video":
            index = select_embedding_representative(
                [vectors[row["id"]] for row in rows],
                top_k=config["classification"]["video_top_k"],
            )
        else:
            if len(rows) != 1:
                raise ValueError(
                    "Still image must have exactly one business encoding input"
                )
            index = 0
        selected[source] = rows[index]["id"]

    # Mirrors _orchestrator._compression input assembly, with no stage-state writes:
    # preferred representative, lexicographic available-member fallback, then unbundled visuals.
    points = []
    covered_visuals = set()
    source_values = prepared["business"]["sources"]
    used_bundles = []

    def point(source, members):
        metadata = source_values[source]
        return CompressionPoint(
            Path(source),
            capture_time=datetime.fromisoformat(metadata["capture_time"])
            if metadata["capture_time"]
            else None,
            gps=tuple(metadata["gps"]) if metadata["gps"] else None,
            embedding=vectors[selected[source]],
            members=tuple(map(Path, members)),
            weight=len(members),
        )

    for bundle in prepared["business"]["bundles"]:
        if not bundle["selected"]:
            continue
        representative = bundle["representative"]
        members = bundle["members"]
        if representative not in selected:
            alternatives = sorted(set(members) & selected.keys())
            if not alternatives:
                continue
            representative = alternatives[0]
        points.append(point(representative, members))
        covered_visuals.update(set(members) & selected.keys())
        used_bundles.append(
            {
                "bundle_id": bundle["id"],
                "representative": representative,
                "preferred_replaced": representative != bundle["representative"],
            }
        )
    for source in sorted(selected.keys() - covered_visuals):
        points.append(point(source, [source]))
    profile = AdaptiveCompressionProfile(**config["classification"]["profile"])
    groups = build_adaptive_groups(points, profile)

    def serializable(value):
        if isinstance(value, Path):
            return value.as_posix()
        if isinstance(value, dict):
            return {key: serializable(item) for key, item in value.items()}
        if isinstance(value, (tuple, list)):
            return [serializable(item) for item in value]
        return value

    values = [serializable(asdict(group)) for group in groups]
    members = [member for group in values for member in group["members"]]
    if len(members) != len(set(members)) or not set(members) <= source_values.keys():
        raise ValueError("Business groups duplicated or invented a source")
    exceptions = sorted(source_values.keys() - set(members))
    for group in values:
        group["representative_input"] = selected[group["representative_path"]]
    return {
        "groups": values,
        "selected_inputs": selected,
        "bundle_selection": used_bundles,
        "exceptions": exceptions,
        "source_count": len(source_values),
        "point_count": len(points),
        "grouped_sources": len(members),
    }
