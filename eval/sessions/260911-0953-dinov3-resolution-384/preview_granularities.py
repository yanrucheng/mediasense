"""Reuse one completed encoding per route for the second, 0.85 granularity."""
import argparse
from pathlib import Path
import subprocess
import sys

parser = argparse.ArgumentParser(description=__doc__)
parser.add_argument("--suffix", default="", help="Suffix of already completed run directories")
args = parser.parse_args()
session = Path(__file__).resolve().parent
root = session.parents[2]
for route in ("384-coreml-batch1", "384-mps", "512-coreml-batch1", "512-mps"):
    subprocess.run([
        sys.executable, str(root / "eval/shared/model_evaluation.py"), "preview",
        "--config", str(session / f"config-{route}-085.json"),
        "--encoding", str(session / "outputs" / (route + args.suffix)),
        "--output", str(session / "outputs" / (route + "-085" + args.suffix)),
        "--summary", str(session / "metrics" / (route + "-085" + args.suffix + ".json")),
    ], cwd=root, check=True)
