"""Compact original cost values; diagnostic timings never enter medians."""

import argparse
import json
from pathlib import Path
from statistics import median

from run import save


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("root", type=Path)
    parser.add_argument("output", type=Path)
    parser.add_argument("--warm-8192-root", type=Path)
    args = parser.parse_args()
    samples, diagnostic = [], []
    for case in ("varied", "local", "diagnostic", "warm-4096", "warm-8192"):
        location = (args.warm_8192_root if case == "warm-8192" and args.warm_8192_root else args.root) / "samples" / case
        assert json.loads((location / "verified.json").read_text())["all_pairs_semantically_equal"]
        for row in json.loads((location / "summary.json").read_text()):
            label, m = row["label"], row["metrics"]
            if m.get("empty") or (case != "varied" and label.endswith("cold")):
                continue
            if case == "varied":
                group = "cold-512" if label.endswith("cold") else "discovery-512" if label.endswith("discovery") else "distinct-warm-512"
            else:
                group = "local-512" if case == "local" else case
            values = {key: m[key] for key in (
                "started_at", "finished_at", "source_unchanged", "all_public_evidence_read",
                "all_members_verified", "direct_correspondence_verified",
                "wall_seconds", "user_seconds", "system_seconds", "read_seconds", "run_plus_read_seconds",
                "result_bytes", "artifact_bytes", "workspace_bytes", "new_attempts", "reused_work",
                "physical_artifacts", "source_count", "evidence_count", "relationship_count", "entry_count",
                "source_identity", "old_result_digests", "result_sha256", "normalized_sha256", "counts",
                "load_before", "load_after", "prior_read_seconds", "audit_seconds", "memory", "pragmas",
            )}
            values["cpu_seconds"] = m["user_seconds"] + m["system_seconds"]
            values["rss_lower_bytes"] = m["memory"]["peak_lower_bound_bytes"]
            values["rss_upper_bytes"] = m["memory"]["peak_upper_bound_bytes"]
            # Mutually exclusive intervals from principal-stage spans. Nested
            # spans belong to their innermost observed stage, never both.
            stages = m["stages"]
            boundaries = sorted({point for span in stages for point in (span["start"], span["end"])})
            exclusive = {}
            for begin, end in zip(boundaries, boundaries[1:]):
                active = [span for span in stages if span["start"] <= begin and span["end"] >= end]
                if active:
                    stage = max(active, key=lambda span: span["start"])["stage"]
                    exclusive[stage] = exclusive.get(stage, 0) + end - begin
            exclusive["other"] = m["wall_seconds"] - sum(exclusive.values())
            assert exclusive["other"] >= 0
            values["exclusive_stage_seconds"] = exclusive
            sample = {"group": group, "label": label, "version": row["version"], "evidence": row["output"], **values}
            if case == "diagnostic":
                sample["sql"] = m["sql"]
                sample["sql_totals"] = {key: sum(phase.get(key, 0) for phase in m["sql"].values()) for key in ("connect", "SELECT", "COMMIT")}
                diagnostic.append(sample)
            else:
                samples.append(sample)
    comparisons = []
    for group in dict.fromkeys(row["group"] for row in samples):
        pair = {version: [row for row in samples if row["group"] == group and row["version"] == version]
                for version in ("baseline", "candidate")}
        assert len(pair["baseline"]) == len(pair["candidate"]) == (3 if group.startswith("warm-") else 1)
        values = {}
        for metric in ("wall_seconds", "cpu_seconds", "rss_lower_bytes", "rss_upper_bytes", "read_seconds", "run_plus_read_seconds", "result_bytes", "artifact_bytes", "workspace_bytes"):
            statistics = {}
            for version, rows in pair.items():
                raw = [row[metric] for row in rows]
                statistics[version] = {"values": raw, "median": median(raw), "min": min(raw), "max": max(raw)}
            baseline = statistics["baseline"]["median"]
            statistics["reduction"] = (baseline - statistics["candidate"]["median"]) / baseline if baseline else None
            values[metric] = statistics
        comparisons.append({"group": group, "repeats_per_version": len(pair["baseline"]), "metrics": values})
    args.output.parent.mkdir(parents=True, exist_ok=True)
    save(args.output, {"comparisons": comparisons, "samples": samples, "diagnostic": diagnostic})
    for row in comparisons:
        metrics = row["metrics"]
        print(row["group"], " | ".join(
            f'{key}: {metrics[key]["baseline"]["median"]:.3f} -> {metrics[key]["candidate"]["median"]:.3f} ({metrics[key]["reduction"]:.1%})'
            for key in ("wall_seconds", "cpu_seconds", "read_seconds")))


if __name__ == "__main__":
    main()
