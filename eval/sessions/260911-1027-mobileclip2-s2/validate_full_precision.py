"""Compare completed CPU FP32 and GPU encodings with the predeclared gate."""

import argparse
import json
from pathlib import Path
import sys
import numpy as np

SESSION = Path(__file__).resolve().parent
sys.path.insert(0, str(SESSION.parents[1] / "shared"))
sys.path.insert(0, str(SESSION.parent / "260910-2212-dinov3-vitb16-512"))
from model_evaluation_inputs import digest, write_json  # noqa: E402
from validate import compare  # noqa: E402

p = argparse.ArgumentParser(description=__doc__)
p.add_argument("--runs", nargs="+", required=True)
p.add_argument("--output", type=Path, required=True)
args = p.parse_args()


def read(name):
    root = SESSION / "outputs" / name
    e = json.loads((root / "encoding.json").read_text())
    rows = json.loads((root / "rows.json").read_text())
    if (
        e["status"] != "encoded"
        or digest(root / "vectors.f32") != e["vectors_sha256"]
        or digest(root / "rows.json") != e["rows_sha256"]
    ):
        raise ValueError("Incomplete/changed run")
    a = np.fromfile(root / "vectors.f32", dtype="<f4").reshape(-1, 512)
    if len(a) != 366 or not np.isfinite(a).all():
        raise ValueError("Invalid vectors")
    if np.max(np.abs(np.linalg.norm(a.astype(np.float64), axis=1) - 1)) > 1e-6:
        raise ValueError("Not unit vectors")
    return a, e, rows


ref, e, rows = read("cpu-fp32")
result = {"reference": "cpu-fp32", "runs": {}, "cross_route": {}}
values = {}
for name in args.runs:
    a, info, mapping = read(name)
    if mapping != rows or info["input_fingerprint"] != e["input_fingerprint"]:
        raise ValueError("Input mapping changed")
    result["runs"][name] = compare(ref, a, enforce=False)
    values[name] = a
for i, name in enumerate(args.runs):
    for other in args.runs[i + 1 :]:
        result["cross_route"][name + "_vs_" + other] = compare(
            values[name], values[other], enforce=False
        )
write_json(args.output, result)
print(json.dumps(result, indent=2))
