"""Audit retained full runs and replay the existing business classifier."""

from __future__ import annotations

import argparse
from html.parser import HTMLParser
import json
import os
from pathlib import Path
import sys
from urllib.parse import unquote, urlsplit

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "shared"))
from model_evaluation_business import classify, check_baseline  # noqa: E402
from model_evaluation_inputs import digest, validate_inputs, write_json  # noqa: E402
from validate import compare  # noqa: E402


def audit_preview(page):
    from PIL import Image

    class Links(HTMLParser):
        def __init__(self):
            super().__init__()
            self.images, self.links, self.sources = set(), set(), []

        def handle_starttag(self, tag, attributes):
            values = dict(attributes)
            if tag == "img" and values.get("src"):
                self.images.add(values["src"])
            if tag == "a" and values.get("href"):
                self.links.add(values["href"])
            if "data-source" in values:
                self.sources.append(values["data-source"])

    parser = Links()
    parser.feed(page.read_text())
    checked = 0
    for target in parser.links | parser.images:
        url = urlsplit(target)
        if url.scheme not in {"", "file"}:
            if target in parser.images:
                raise ValueError("Preview attempts to load a remote image")
            continue
        if not url.path:
            continue
        path = Path(unquote(url.path))
        if not path.is_absolute():
            path = page.parent / path
        if not path.is_file():
            raise ValueError(f"Missing preview target: {path}")
        checked += 1
        if target in parser.images:
            with Image.open(path) as image:
                image.verify()
    if len(parser.sources) != 2134 or len(set(parser.sources)) != 2134:
        raise ValueError("Preview omitted or duplicated source cards")
    return {"source_cards": len(parser.sources), "unique_sources": len(set(parser.sources)), "decoded_unique_images": len(parser.images), "existing_local_targets": checked}


def read_run(path, prepared):
    import numpy as np

    encoding = json.loads((path / "encoding.json").read_text())
    config = json.loads((path / "config.json").read_text())
    rows = json.loads((path / "rows.json").read_text())
    if encoding["status"] != "encoded":
        raise ValueError(f"Run is incomplete: {path}")
    for filename, key in [("rows.json", "rows_sha256"), ("vectors.f32", "vectors_sha256")]:
        if digest(path / filename) != encoding[key]:
            raise ValueError(f"Retained artifact changed: {path / filename}")
    if [r["id"] for r in rows] != [r["id"] for r in prepared["inputs"]]:
        raise ValueError("Input order/identity changed")
    encoded = [row for row in rows if row["state"] == "encoded"]
    array = np.fromfile(path / "vectors.f32", dtype="<f4").reshape(-1, config["model"]["dimensions"])
    if len(array) != 366 or sorted(row["vector_row"] for row in encoded) != list(range(366)):
        raise ValueError("Expected 366 uniquely mapped vectors")
    if not np.isfinite(array).all():
        raise ValueError("Nonfinite retained vector")
    norm_error = float(np.max(np.abs(np.linalg.norm(array.astype(np.float64), axis=1) - 1)))
    if norm_error > 1e-6:
        raise ValueError("Stored normalization tolerance failed")
    vectors = {row["id"]: tuple(float(x) for x in array[row["vector_row"]]) for row in encoded}
    groups = json.loads((path / "preview/groups.json").read_text())
    check_baseline(config, prepared)
    replay = classify(config, prepared, vectors)
    if replay != groups:
        raise ValueError("Stored vectors do not reproduce the business result")
    info = {
        "vectors": len(array), "dimensions": array.shape[1], "max_unit_norm_error": norm_error,
        "reclassification_exact": True, "groups": len(groups["groups"]),
        "source_count": groups["source_count"], "grouped_sources": groups["grouped_sources"],
        "source_exceptions": len(groups["exceptions"]),
        "single_candidate_groups": sum(g["basis"]["candidate_point_count"] == 1 for g in groups["groups"]),
        "selected_sources": len(groups["selected_inputs"]),
        "input_failures": sum(r["state"] == "input_failed" for r in rows),
        "vectors_sha256": encoding["vectors_sha256"],
        "preview_integrity": audit_preview(path / "preview/index.html"),
    }
    if info["source_count"] != 2134 or info["grouped_sources"] != 2134 or info["input_failures"] != 185:
        raise ValueError("Frozen source/failure accounting changed")
    return array, groups, info


def business_signature(result):
    return {
        "groups": [{key: group[key] for key in ("members", "representative_path", "representative_input", "boundary_paths", "outlier_paths", "conflict_paths")} for group in result["groups"]],
        "selected_inputs": result["selected_inputs"],
        "bundle_selection": result["bundle_selection"],
        "exceptions": result["exceptions"],
    }


def compare_groups(candidate, baseline):
    a = [set(g["members"]) for g in candidate["groups"]]
    b = [set(g["members"]) for g in baseline["groups"]]
    exact = [(i, j) for i, members in enumerate(a) for j, other in enumerate(b) if members == other]
    splits = []
    for j, members in enumerate(b):
        overlaps = [i for i, other in enumerate(a) if members & other]
        if len(overlaps) > 1:
            splits.append({"baseline_group": j + 1, "source_count": len(members), "candidate_groups": [i + 1 for i in overlaps]})
    return {
        "candidate_groups": len(a), "baseline_groups": len(b),
        "exact_membership_matches": len(exact),
        "changed_representatives_in_exact_matches": sum(candidate["groups"][i]["representative_input"] != baseline["groups"][j]["representative_input"] for i, j in exact),
        "candidate_groups_within_one_baseline_group": sum(any(members <= other for other in b) for members in a),
        "baseline_groups_spanning_multiple_candidate_groups": len(splits),
        "selected_inputs_equal": candidate["selected_inputs"] == baseline["selected_inputs"],
        "review_examples": sorted(splits, key=lambda x: len(x["candidate_groups"]), reverse=True)[:5],
        "quality_judgment": "pending human review; these counts only locate differences",
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--config", type=Path, required=True)
    parser.add_argument("--inputs", type=Path, required=True)
    parser.add_argument("--runs", type=Path, nargs="+", required=True, help="First run is the MPS reference")
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    os.environ.update(OPENBLAS_NUM_THREADS="2", OMP_NUM_THREADS="2")
    config = json.loads(args.config.read_text())
    prepared = validate_inputs(config, args.inputs)
    values = [read_run(path, prepared) for path in args.runs]
    result = {"input_fingerprint": prepared["input_fingerprint"], "runs": {str(path): value[2] for path, value in zip(args.runs, values, strict=True)}, "cross_route": {}}
    for path, value in zip(args.runs[1:], values[1:], strict=True):
        numerical = compare(values[0][0], value[0], enforce=False)
        result["cross_route"][str(path)] = {"numerical": numerical, "business_equal_including_frontiers": business_signature(values[0][1]) == business_signature(value[1])}
    result["all_cross_route_numerical_gates_passed"] = all(v["numerical"]["passed"] for v in result["cross_route"].values())
    for label, path in [
        ("siglip2", "eval/sessions/260910-1717-siglip2-so400m-512/outputs/mps/preview/groups.json"),
        ("chineseclip", "eval/sessions/260910-1330-chineseclip-business-baseline/outputs/baseline/preview/groups.json"),
    ]:
        result["versus_" + label] = compare_groups(values[0][1], json.loads(Path(path).read_text()))
    write_json(args.output, result)
    print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
