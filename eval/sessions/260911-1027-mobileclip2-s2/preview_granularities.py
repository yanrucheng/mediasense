"""Generate the fixed 0.85 preview by replaying each completed encoding."""
import argparse
from pathlib import Path
import subprocess
import sys

session=Path(__file__).resolve().parent
root=session.parents[2]
p=argparse.ArgumentParser(description=__doc__)
p.add_argument("--suffix",default="")
args=p.parse_args()
for route in ("coreml-fp32","mps-fp32"):
    subprocess.run([sys.executable,str(root/"eval/shared/model_evaluation.py"),"preview",
        "--config",str(session/f"config-{route}-085.json"),
        "--encoding",str(session/"outputs"/(route+args.suffix)),
        "--output",str(session/"outputs"/(route+"-085"+args.suffix)),
        "--summary",str(session/"metrics"/(route+"-085"+args.suffix+".json"))],cwd=root,check=True)
