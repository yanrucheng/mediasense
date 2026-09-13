"""Replay retained HK compression through the real producer in an isolated copy."""

import argparse
from collections import Counter, defaultdict
import hashlib
import json
from pathlib import Path
import shutil
import sqlite3


def subject(record):
    from mediasense.precheck._compression_producer import (
        _record_subject,
        _record_source_paths,
    )

    direct = record.output.get("subject", {}).get("relative_path")
    return (
        Path(direct)
        if direct
        else _record_subject(record) or sorted(_record_source_paths(record))[0]
    )


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--database", type=Path, required=True)
    parser.add_argument("--run-id", required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    args.output.mkdir(parents=True, exist_ok=False)
    private = args.output / "work.sqlite3"
    with sqlite3.connect(
        args.database.resolve().as_uri() + "?mode=ro", uri=True
    ) as original:
        with sqlite3.connect(private) as copy:
            original.backup(copy)
    from mediasense.precheck import (
        AccountingStore,
        AdaptiveCompressionProducer,
        AdaptiveCompressionProfile,
        CompressionInput,
    )
    from mediasense.precheck.work import WorkStore
    from mediasense.precheck._compression_producer import (
        _record_source_paths,
        _record_subject,
    )

    with sqlite3.connect(private) as db:
        dataset_id = db.execute(
            "SELECT dataset_id FROM working_runs WHERE run_id=?", (args.run_id,)
        ).fetchone()[0]
    AccountingStore(private).register_dataset(dataset_id)
    attached = {r.work_id: r for r in WorkStore(private).list_run_work(args.run_id)}
    by_cap = defaultdict(list)
    for r in attached.values():
        if r.status == "succeeded":
            by_cap[r.spec.capability].append(r)
    visual = {}
    for r in by_cap["image-rendition"]:
        path = subject(r)
        if (
            path not in visual
            or r.output["value"]["profile"]["name"] == "high_resolution"
        ):
            visual[path] = r
    for r in by_cap["video-key-frame-candidate"]:
        visual[_record_subject(r)] = attached[
            r.output["candidate"]["selected_frame_work_id"]
        ]
    for r in by_cap["video-contact-sheet"]:
        visual.setdefault(subject(r), r)
    metadata = {subject(r): r for r in by_cap["source-metadata"]}
    gpx = {subject(r): r for r in by_cap["gpx-location-candidate"]}
    embeddings = {
        r.output["value"]["input_work_id"]: r for r in by_cap["image-embedding"]
    }
    producer = AdaptiveCompressionProducer(private)
    inputs, covered = [], set()

    def add(path, members, bundle=None):
        image = visual[path]
        embedding = embeddings.get(image.work_id)
        if embedding:
            for artifact in producer.artifacts.artifacts_for_work(
                embedding.work_id, verify=False
            ):
                target = artifact.path
                target.parent.mkdir(parents=True, exist_ok=True)
                shutil.copyfile(
                    args.database.parent / artifact.path.relative_to(args.output),
                    target,
                )
        inputs.append(
            CompressionInput(
                path,
                image.work_id,
                tuple(members),
                None if bundle is None else bundle.work_id,
                metadata[path].work_id if path in metadata else None,
                gpx[path].work_id if path in gpx else None,
                embedding.work_id if embedding else None,
            )
        )

    for r in by_cap["bundle-candidate"]:
        members = _record_source_paths(r)
        path = Path(r.output["candidate"]["representative_path"])
        if path not in visual:
            alternatives = sorted(p for p in members if p in visual)
            if not alternatives:
                continue
            path = alternatives[0]
        add(path, members, r)
        covered.update(p for p in members if p in visual)
    for path in visual:
        if path not in covered:
            add(path, (path,))

    prepared = [producer._prepare_input(args.run_id, i, attached)[0] for i in inputs]
    saved = by_cap["adaptive-compression-group"]
    profile = AdaptiveCompressionProfile(**saved[0].output["profile"])
    assert profile.content_distance_scale == 0.311
    outcomes = producer.produce(args.run_id, inputs, profile=profile)
    expected_ids = {r.output["group"]["group_id"] for r in saved}
    assert {o.group.group_id for o in outcomes} == expected_ids
    old_by_group = {r.output["group"]["group_id"]: r for r in saved}
    changed_limits = sum(
        o.group.qualifications
        != tuple(old_by_group[o.group.group_id].output["group"]["qualifications"])
        for o in outcomes
    )
    assert all(
        o.work.output["group"]["qualifications"] == list(o.group.qualifications)
        for o in outcomes
    )
    repeated = producer.produce(args.run_id, inputs, profile=profile)
    assert all(o.reused for o in repeated)
    metrics = {
        "inputs": len(inputs),
        "coordinates_consumed": sum(p.gps is not None for p in prepared),
        "gpx_only_consumed": sum(
            p.gps is not None
            and i.gpx_work_id is not None
            and not any(
                o["name"] == "gps_coordinates" and o["status"] == "available"
                for o in attached[i.metadata_work_id].output["observations"]
            )
            for i, p in zip(inputs, prepared)
        ),
        "groups": len(outcomes),
        "identical_group_ids": True,
        "changed_qualifications": changed_limits,
        "prior_qualifications": dict(
            Counter(q for r in saved for q in r.output["group"]["qualifications"])
        ),
        "qualifications": dict(
            Counter(q for o in outcomes for q in o.group.qualifications)
        ),
        "reused_old_groups": sum(o.reused for o in outcomes),
        "reused_on_repeat": sum(o.reused for o in repeated),
        "content_distance_scale": profile.content_distance_scale,
        "membership_digest": hashlib.sha256(
            json.dumps(sorted(expected_ids)).encode()
        ).hexdigest(),
    }
    assert metrics["inputs"] == 167 and metrics["gpx_only_consumed"] == 55
    assert (
        metrics["groups"] == 156
        and metrics["qualifications"]["limited_similarity_evidence"] == 21
    )
    (args.output / "metrics.json").write_text(json.dumps(metrics, indent=2) + "\n")
    print(json.dumps(metrics, indent=2))


if __name__ == "__main__":
    main()
