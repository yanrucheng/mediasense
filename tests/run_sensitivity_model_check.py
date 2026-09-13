"""Compare only the five authorized development inputs through installed adapters."""

import argparse
from dataclasses import asdict
import hashlib
import json
from pathlib import Path
import socket
import sys

import mediasense
from mediasense.precheck._sensitivity_models import LocalSensitivityDetector
from mediasense.precheck._sensitivity_profiles import PROFILES, SensitivityInput
from mediasense.precheck._sensitivity_values import validate_named_value

IDS = ["sample-0001", "sample-0002", "sample-0011", "sample-0013", "sample-0104"]
REFS = {
    "freepik": (
        "runs/classification/freepik-mps-fp32-b4-dev-001/results.jsonl",
        "6ff7b65f0d01c6c2d95a1c9710f4e9e49f57541f818acaf5339a05f4d7232caa",
    ),
    "nudenet640": (
        "runs/detection/nudenet640-native-dev-001/results.jsonl",
        "49c875748ca9baf8783c9cb0ad1c7d9bb82c6de0e648f094d7bf8b1fa7749341",
    ),
}


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--evidence", type=Path, required=True)
    p.add_argument("--models", type=Path, required=True)
    p.add_argument("--output", type=Path, required=True)
    args = p.parse_args()
    args.output.mkdir(exist_ok=False)
    assert "/site-packages/" in str(Path(mediasense.__file__).resolve()), (
        mediasense.__file__
    )
    rows = {
        r["sample_id"]: r
        for r in map(
            json.loads,
            (args.evidence / "prepared/development.jsonl").read_text().splitlines(),
        )
    }
    inputs = []
    for key in IDS:
        r = rows[key]
        assert r["split"] == "development" and r["status"] == "ready"
        path = args.evidence / r["path"]
        assert digest(path) == r["sha256"]
        inputs.append(SensitivityInput(key, path, r["sha256"], r["width"], r["height"]))
    network_attempts = []

    def deny(*args, **kwargs):
        network_attempts.append(repr(args)[:200])
        raise AssertionError("No network allowed in sensitivity acceptance")

    socket.socket.connect = deny
    socket.create_connection = deny
    report = {
        "python": sys.executable,
        "loaded_from": mediasense.__file__,
        "inputs": IDS,
        "models": {},
        "network_attempts": network_attempts,
    }
    try:
        for name, profile in PROFILES.items():
            reference_path, expected = REFS[name]
            path = args.evidence / reference_path
            assert digest(path) == expected
            reference = {
                r["sample_id"]: r
                for r in map(json.loads, path.read_text().splitlines())
            }
            model = LocalSensitivityDetector(
                profile, args.models / ("freepik" if name == "freepik" else "640m.onnx")
            )
            values, differences, batches = [], [], []
            try:
                for start in range(0, len(inputs), profile.batch_size):
                    batch = inputs[start : start + profile.batch_size]
                    predictions = model.analyze(batch)
                    batches.append([i.key for i in batch])
                    for prediction in predictions:
                        assert prediction.failure is None
                        validate_named_value(
                            {
                                "detector_identity": model.identity,
                                "profile": profile.name,
                                **prediction.values,
                            },
                            profile.definitions,
                            profile.basis,
                        )
                        ref = reference[prediction.key]
                        assert prediction.sha256 == ref["input_sha256"]
                        if name == "freepik":
                            for actual, prior in [
                                (
                                    prediction.values["classification_distribution"][
                                        "probabilities"
                                    ],
                                    ref["raw_output"]["probabilities"],
                                ),
                                (
                                    prediction.values["cumulative_probabilities"],
                                    ref["raw_output"]["cumulative_probabilities"],
                                ),
                            ]:
                                assert set(actual) == set(prior)
                                diff = max(abs(actual[k] - prior[k]) for k in actual)
                                differences.append(diff)
                                assert diff <= 1e-5, (prediction.key, diff)
                        else:
                            actual = sorted(
                                prediction.values["region_detections"]["instances"],
                                key=lambda b: (b["label"], b["box_xyxy"]),
                            )
                            prior = sorted(
                                ref["boxes"], key=lambda b: (b["label"], b["xyxy"])
                            )
                            assert len(actual) == len(prior), (
                                prediction.key,
                                len(actual),
                                len(prior),
                            )
                            for a, b in zip(actual, prior, strict=True):
                                assert (
                                    a["label"] == b["label"]
                                    and a["box_xyxy"] == b["xyxy"]
                                ), (prediction.key, a, b)
                                diff = abs(a["score"] - b["score"])
                                differences.append(diff)
                                assert diff <= 1e-6, (prediction.key, diff)
                        values.append(asdict(prediction))
                report["models"][name] = {
                    "identity": model.identity,
                    "execution": model.execution,
                    "batches": batches,
                    "max_absolute_difference": max(differences),
                    "predictions": values,
                    "reference_sha256": expected,
                }
            finally:
                model.close()
        for item in inputs:
            assert digest(item.path) == item.sha256
        assert not network_attempts
        report["status"] = "passed"
    except Exception as error:
        report["status"] = "failed"
        report["error"] = repr(error)
        raise
    finally:
        (args.output / "report.json").write_text(json.dumps(report, indent=2))
    print(
        json.dumps(
            {
                k: {
                    "max_absolute_difference": v["max_absolute_difference"],
                    "batches": v["batches"],
                }
                for k, v in report["models"].items()
            },
            indent=2,
        )
    )


if __name__ == "__main__":
    main()
