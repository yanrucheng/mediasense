"""Validate retained vectors, business replay and browser assets for this session."""

import argparse
import json
from pathlib import Path
import sys

SESSION = Path(__file__).resolve().parent
sys.path.insert(0, str(SESSION.parents[1] / "shared"))
sys.path.insert(0, str(SESSION.parent / "260910-2212-dinov3-vitb16-512"))
from model_evaluation_inputs import validate_inputs, write_json  # noqa: E402
from model_evaluation_preview import read_encoding  # noqa: E402
from model_evaluation_business import classify  # noqa: E402
from validate_results import read_run, audit_preview, compare_groups, business_signature  # noqa: E402
from validate import compare  # noqa: E402

p = argparse.ArgumentParser(description=__doc__)
p.add_argument("--suffix", default="")
p.add_argument("--routes", nargs=2, default=["mps-fp32", "coreml-fp32"])
args = p.parse_args()
c = json.loads((SESSION / "config-mps.json").read_text())
data = validate_inputs(
    c,
    SESSION.parent
    / "260910-1330-chineseclip-business-baseline/outputs/prepared/inputs.json",
)
values = {}
result = {"status": "incomplete", "runs": {}, "comparisons": {}, "previews": {}}
for route in args.routes:
    output = SESSION / "outputs" / (route + args.suffix)
    a, g, info = read_run(output, data)
    values[route] = (a, g)
    result["runs"][route] = info
    e = json.loads((output / "encoding.json").read_text())
    perf = e["performance"]
    if abs(sum(perf["stage_seconds"].values()) - perf["encoding_seconds"]) > 1e-8:
        raise ValueError("Stage time accounting differs")
    coarse = SESSION / "outputs" / (route + "-085" + args.suffix)
    cc = json.loads((coarse / "config.json").read_text())
    _, _, _, vectors = read_encoding(cc, output)
    groups = json.loads((coarse / "preview/groups.json").read_text())
    if groups != classify(cc, data, vectors):
        raise ValueError("Coarse replay differs")
    result["previews"][route + "-085"] = {
        "integrity": audit_preview(coarse / "preview/index.html"),
        "groups": len(groups["groups"]),
    }
    values[route + "-085"] = groups
    for suffix in ("", "-085"):
        current = groups if suffix else g
        old = (
            SESSION.parent
            / "260911-0953-dinov3-resolution-384"
            / "outputs"
            / ("384-" + ("mps" if route.startswith("mps") else "coreml-batch1") + suffix)
            / "preview/groups.json"
        )
        result["comparisons"][route + suffix + "_vs_dino384"] = compare_groups(
            current, json.loads(old.read_text())
        )
result["numerical"] = compare(values[args.routes[0]][0], values[args.routes[1]][0], enforce=False)
result["runtime_business_equal_0311"] = business_signature(
    values[args.routes[0]][1]
) == business_signature(values[args.routes[1]][1])
result["runtime_business_equal_085"] = business_signature(
    values[args.routes[0]+"-085"]
) == business_signature(values[args.routes[1]+"-085"])
result["status"] = (
    "passed" if result["numerical"]["passed"] else "numerical_gate_failed"
)
write_json(SESSION / "metrics" / ("result-validation" + args.suffix + ".json"), result)
print(json.dumps(result, ensure_ascii=False, indent=2))
