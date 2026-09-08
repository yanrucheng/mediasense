"""Read-only compact comparison of the replay and the exact audited Result."""

import argparse
from collections import Counter
from datetime import datetime
import json
from pathlib import Path
import sqlite3


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--baseline-result", type=Path, required=True)
    parser.add_argument("--prefix", default="final-")
    args = parser.parse_args()
    old = json.loads(args.baseline_result.read_text())
    old_times = {}
    for source in old["sources"]:
        if not source["relative_path"].startswith("260501-HK美食之旅/"):
            continue
        relative = source["relative_path"].split("/", 1)[1]
        for observation in source["view"].get("observations", []):
            if (
                observation["name"] == "capture_time"
                and observation["status"] == "available"
            ):
                old_times[relative] = observation["value"]
    summaries = []
    for label in ("without-embedding", "with-embedding", "embedding-reuse"):
        metric = json.loads((args.output / (args.prefix + label + ".json")).read_text())
        metric.pop("group_members")
        summaries.append(metric)
    database = args.output / "workspace/precheck/work.sqlite3"
    deltas, qualifications, selected_tags = Counter(), Counter(), Counter()
    examples = []
    with sqlite3.connect(database.as_uri() + "?mode=ro", uri=True) as db:
        run_id = db.execute(
            "SELECT accounting_run_id FROM precheck_runs WHERE run_ref=?",
            (summaries[-1]["run_ref"],),
        ).fetchone()[0]
        rows = db.execute(
            "SELECT w.output_json FROM work_records w JOIN run_work_records r USING(work_id) WHERE r.run_id=? AND w.capability='source-metadata'",
            (run_id,),
        )
        for (output,) in rows:
            value = json.loads(output)
            relative = value["subject"]["relative_path"]
            capture = next(
                item for item in value["observations"] if item["name"] == "capture_time"
            )
            selected_tags[capture.get("provenance", {}).get("tag", "missing")] += 1
            qualifications.update(q["code"] for q in capture.get("qualifications", []))
            if relative in old_times and capture["status"] == "available":
                delta = (
                    datetime.fromisoformat(capture["value"])
                    - datetime.fromisoformat(old_times[relative])
                ).total_seconds()
                deltas[str(delta)] += 1
                if "20260504173346" in relative or "20260504202728" in relative:
                    examples.append(
                        {
                            "path": relative,
                            "old": old_times[relative],
                            "new": capture["value"],
                            "basis": capture["provenance"],
                        }
                    )
    print(
        json.dumps(
            {
                "runs": summaries,
                "capture_time_delta_seconds": deltas,
                "capture_time_qualifications": qualifications,
                "selected_tags": selected_tags,
                "examples": examples,
            },
            ensure_ascii=False,
            indent=2,
        )
    )


if __name__ == "__main__":
    main()
