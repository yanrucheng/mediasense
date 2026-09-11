"""Audit four fresh encodings and eight previews without quality scoring."""
import argparse
import json
from pathlib import Path
import sys

import numpy as np

SESSION = Path(__file__).resolve().parent
ROOT = SESSION.parents[2]
sys.path.insert(0, str(ROOT / "eval/shared"))
sys.path.insert(0, str(SESSION.parent / "260910-2212-dinov3-vitb16-512"))
from model_evaluation import inference_fingerprint  # noqa: E402
from model_evaluation_inputs import digest, validate_inputs, write_json  # noqa: E402
from model_evaluation_preview import read_encoding  # noqa: E402
from model_evaluation_business import classify  # noqa: E402
from validate import compare  # noqa: E402
from validate_results import audit_preview, business_signature, compare_groups, read_run  # noqa: E402

parser = argparse.ArgumentParser(description=__doc__)
parser.add_argument("--suffix", default="")
args = parser.parse_args()
suffix = args.suffix
config = json.loads((SESSION / "config-384-mps.json").read_text())
prepared = validate_inputs(config, ROOT / "eval/sessions/260910-1330-chineseclip-business-baseline/outputs/prepared/inputs.json")
result = {"status": "incomplete", "runs": {}, "previews": {}, "numerical_384": {}, "resolution_comparison": {}}
values = {}
for route in ("384-mps", "384-coreml-batch1", "512-mps", "512-coreml-batch1"):
    output = SESSION / "outputs" / (route + suffix)
    values[route] = read_run(output, prepared)
    result["runs"][route] = values[route][2]
    c = json.loads((output / "config.json").read_text())
    e = json.loads((output / "encoding.json").read_text())
    if e["inference_fingerprint"] != inference_fingerprint(c):
        raise ValueError("Encoding identity mismatch")
    perf = e["performance"]
    if not np.isclose(sum(perf["stage_seconds"].values()), perf["encoding_seconds"], atol=1e-10, rtol=0):
        raise ValueError("Stage timings do not sum to total")
    if perf["encoded_inputs"] != 366 or perf["embedding_cache_hits"] or perf["warmup_inputs"]:
        raise ValueError("Performance did not encode the complete fresh input set")
    coarse = SESSION / "outputs" / (route + "-085" + suffix)
    cc = json.loads((coarse / "config.json").read_text())
    _, _, _, vectors = read_encoding(cc, output)
    groups = json.loads((coarse / "preview/groups.json").read_text())
    if groups != classify(cc, prepared, vectors):
        raise ValueError("Reused vectors do not reproduce coarse preview")
    summary = json.loads((SESSION / "metrics" / (route + "-085" + suffix + ".json")).read_text())
    if summary["performance"] is not None or summary["encoding_reuse"]["newly_encoded"] != 0 or summary["encoding_reuse"]["source_vectors_sha256"] != e["vectors_sha256"]:
        raise ValueError("Replay misrepresents performance/provenance")
    result["previews"][route + "-085"] = {"groups": len(groups["groups"]), "integrity": audit_preview(coarse / "preview/index.html"), "new_inference": False}
    values[route + "-085"] = groups

result["numerical_384"] = compare(values["384-mps"][0], values["384-coreml-batch1"][0])
for scale in ("", "-085"):
    a = values["384-mps" + scale] if scale else values["384-mps"][1]
    b = values["384-coreml-batch1" + scale] if scale else values["384-coreml-batch1"][1]
    result["previews"]["384_runtime_business_equal" + scale] = business_signature(a) == business_signature(b)
    for runtime in ("mps", "coreml-batch1"):
        a = values["384-" + runtime + scale] if scale else values["384-" + runtime][1]
        b = values["512-" + runtime + scale] if scale else values["512-" + runtime][1]
        result["resolution_comparison"][runtime + scale] = compare_groups(a, b)
# Timing instrumentation must not alter the established 512 features. This does
# not compare the accepted 103/104 grouping difference or impose equality on 384.
for runtime, old in (("mps", "mps"), ("coreml-batch1", "coreml-batch1")):
    previous = SESSION.parent / "260910-2212-dinov3-vitb16-512" / "outputs" / old
    e = json.loads((previous / "encoding.json").read_text())
    if digest(previous / "vectors.f32") != e["vectors_sha256"]:
        raise ValueError("Historical vectors changed")
    previous_array = np.fromfile(previous / "vectors.f32", dtype="<f4").reshape(366, 768)
    result["runs"]["512-" + runtime]["vs_historical_512"] = compare(previous_array, values["512-" + runtime][0])
    if np.array_equal(values["384-" + runtime][0], values["512-" + runtime][0]):
        raise ValueError("384 unexpectedly reused 512 vectors")
result["status"] = "passed"
write_json(SESSION / "metrics" / ("result-validation" + suffix + ".json"), result)
print(json.dumps({"status": result["status"], "numerical_384": result["numerical_384"], "resolution_comparison": result["resolution_comparison"]}, ensure_ascii=False, indent=2))
