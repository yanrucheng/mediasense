"""Restore owned templates at their original address; archive every sample."""

import argparse
import json
import os
from pathlib import Path
import shutil
import subprocess
from time import perf_counter

from run import canonical, digest, save


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, required=True)
    parser.add_argument("--output-root", type=Path)
    parser.add_argument("--reuse-templates", action="store_true")
    parser.add_argument("--baseline", type=Path, required=True)
    parser.add_argument("--candidate", type=Path, required=True)
    parser.add_argument("--python", type=Path, required=True)
    parser.add_argument("--case", choices=("pilot", "varied", "local", "warm-4096", "warm-8192", "diagnostic"), required=True)
    parser.add_argument("--resume-after-audit-fix", action="store_true")
    args = parser.parse_args()
    root = args.root.resolve()
    root.mkdir(parents=True, exist_ok=True)
    slot = root / "slots" / args.case
    if args.reuse_templates:
        assert slot.is_dir()
    else:
        slot.mkdir(parents=True, exist_ok=args.resume_after_audit_fix)
    marker = slot / "owned-test-slot.json"
    if args.resume_after_audit_fix or args.reuse_templates:
        assert marker.exists()
    else:
        save(marker, {"purpose": "precheck-efficiency-same-address-restoration", "workspace": str(slot / "workspace")})
    templates = root / "templates" / args.case
    templates.mkdir(parents=True, exist_ok=args.resume_after_audit_fix or args.reuse_templates)
    outputs = (args.output_root.resolve() if args.output_root else root) / "samples" / args.case
    outputs.mkdir(parents=True, exist_ok=args.resume_after_audit_fix)
    versions = {"baseline": args.baseline.resolve(), "candidate": args.candidate.resolve()}
    flags = []
    size = 8 if args.case == "pilot" else int(args.case.split("-")[1]) if args.case.startswith("warm-") else 512
    if args.case in {"varied", "pilot", "diagnostic"}:
        flags.append("--varied")
    if args.case == "local":
        flags.append("--local")
    results = json.loads((outputs / "summary.json").read_text()) if args.resume_after_audit_fix else []

    def launch(version, label, extra=()):
        output = outputs / label
        environment = dict(os.environ)
        environment["PYTHONPATH"] = str(versions[version] / "src")
        command = [str(args.python.absolute()), str(Path(__file__).with_name("run.py")),
                   "--slot", str(slot), "--output", str(output), "--size", str(size), *flags, *extra]
        print(canonical({"launch": label, "version": version, "size": size}), flush=True)
        with (outputs / (label + ".log")).open("w") as log:
            process = subprocess.run(command, env=environment, stdout=log, stderr=subprocess.STDOUT)
        # Retain failed samples too; never overwrite their workspace evidence.
        output.mkdir(exist_ok=True)
        start = perf_counter()
        if (slot / "workspace").exists():
            shutil.copytree(slot / "workspace", output / "workspace")
        archive_seconds = perf_counter() - start
        save(output / "invocation.json", {"command": command, "version": version, "code": str(versions[version]),
             "returncode": process.returncode, "archive_seconds": archive_seconds,
             "script_sha256": digest(Path(__file__).with_name("run.py")), "driver_sha256": digest(__file__)})
        assert process.returncode == 0, str(outputs / (label + ".log"))
        metrics = json.loads((output / "metrics.json").read_text())
        results.append({"label": label, "version": version, "metrics": metrics, "output": str(output)})
        save(outputs / "summary.json", results)
        return output

    def restore(template):
        assert json.loads(marker.read_text())["workspace"] == str(slot / "workspace")
        start = perf_counter()
        shutil.rmtree(slot / "workspace")
        shutil.copytree(template, slot / "workspace")
        with (outputs / "restores.jsonl").open("a") as stream:
            stream.write(canonical({"template": str(template), "seconds": perf_counter() - start}) + "\n")

    def compare(left, right):
        assert digest(left / "normalized.json") == digest(right / "normalized.json"), f"semantic difference: {left} vs {right}"

    if not args.resume_after_audit_fix and not args.reuse_templates:
        launch("baseline", "empty", ("--empty",))
        shutil.copytree(slot / "workspace", templates / "empty")
        baseline_cold = launch("baseline", "baseline-cold")
        shutil.copytree(slot / "workspace", templates / "warm")
    if args.case in {"varied", "pilot"}:
        if args.reuse_templates:
            restore(templates / "empty")
            baseline_cold = launch("baseline", "baseline-cold")
        restore(templates / "empty")
        candidate_cold = launch("candidate", "candidate-cold")
        compare(baseline_cold, candidate_cold)
    repeats = 3 if args.case.startswith("warm-") else 1
    for index in range(repeats):
        pair = {}
        for version in (("baseline", "candidate") if index % 2 == 0 else ("candidate", "baseline")):
            restore(templates / "warm")
            label = f"{version}-warm-{index + 1}" + ("-audit-fixed" if args.resume_after_audit_fix else "")
            pair[version] = launch(version, label, ("--diagnostic",) if args.case == "diagnostic" else ())
        compare(pair["baseline"], pair["candidate"])
    if args.case == "varied":
        pair = {}
        for version in ("baseline", "candidate"):
            restore(templates / "warm")
            pair[version] = launch(version, version + "-discovery", ("--discovery",))
        compare(pair["baseline"], pair["candidate"])
    save(outputs / "verified.json", {"all_pairs_semantically_equal": True, "sample_count": len(results),
         "templates": str(templates), "restore_location": str(slot / "workspace")})


if __name__ == "__main__":
    main()
