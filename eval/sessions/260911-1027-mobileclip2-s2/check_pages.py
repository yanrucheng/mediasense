"""Open all delivered pages in the existing local WebKit checker."""
import argparse
import json
from pathlib import Path
import subprocess

session = Path(__file__).resolve().parent
parser = argparse.ArgumentParser(description=__doc__)
parser.add_argument("--checker", default="/private/tmp/mediasense-dinov3-260910/check-preview")
parser.add_argument("--suffix", default="")
args = parser.parse_args()
summary_path = session / "metrics" / ("browser-validation" + args.suffix + ".json")
if summary_path.exists():
    raise ValueError("Use a new suffix; browser evidence must not be overwritten")
results = {}
for route in ("coreml-fp32", "mps-fp32"):
    for scale in ("", "-085"):
        name = route + scale + args.suffix
        summary = json.loads((session / "metrics" / (name + ".json")).read_text())
        output = subprocess.check_output([
            args.checker, str(session / "outputs" / name / "preview/index.html"),
            str(session / "outputs" / ("browser-" + name + ".png")),
        ], text=True, timeout=55)
        value = json.loads(output.strip().splitlines()[-1])
        if not (value["groups"] == summary["counts"]["groups"] and value["source_cards"] == 2134 and value["expanded"] and value["collapsed"] and value["video_expanded"] and value["decoded_images"] == value["checked_images"] == 16):
            raise ValueError(f"Browser check failed: {name}: {value}")
        results[name] = value
        print(name, value["groups"], "passed", flush=True)
with summary_path.open("x") as stream:
    stream.write(json.dumps(results, indent=2) + "\n")
