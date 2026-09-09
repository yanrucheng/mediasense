from __future__ import annotations

from pathlib import Path
from datetime import datetime, timedelta, timezone
import math

from PIL import Image, ImageStat

from mediasense.precheck import (
    AccountingStore,
    AdaptiveCompressionProducer,
    AdaptiveCompressionProfile,
    BundleCandidateProducer,
    CompressionInput,
    CompressionPoint,
    EmbeddingProducer,
    EmbeddingProfile,
    ImageRenditionProducer,
    PrecheckReadTool,
    ResultStore,
    WorkStatus,
    build_adaptive_groups,
)


def test_content_boundaries_reduce_duplicates_and_preserve_rare_change_over_budget():
    points = tuple(
        CompressionPoint(
            Path(f"item-{i}.jpg"),
            datetime(2026, 5, 1, tzinfo=timezone.utc) + timedelta(minutes=2 * i),
            embedding=vector,
        )
        for i, vector in enumerate([(1, 0)] * 5 + [(0, 1)] + [(1, 0)] * 5)
    )
    profile = AdaptiveCompressionProfile(
        target_entries=1, content_based_boundaries=True
    )
    groups = build_adaptive_groups(points, profile)
    assert len(groups) == 3
    assert groups[1].members == (Path("item-5.jpg"),)
    assert sum(len(group.members) for group in groups) == 11
    assert sum(group.basis["representative_comparison_count"] for group in groups) > 0
    assert len(build_adaptive_groups(points[:5], profile)) == 1


def test_content_boundaries_detect_drift_and_missing_evidence_remains_visible():
    points = tuple(
        CompressionPoint(
            Path(f"item-{i}.jpg"), embedding=(math.cos(i * 0.2), math.sin(i * 0.2))
        )
        for i in range(10)
    )
    groups = build_adaptive_groups(
        points,
        AdaptiveCompressionProfile(target_entries=1, content_based_boundaries=True),
    )
    assert len(groups) >= 2
    missing = build_adaptive_groups(
        [CompressionPoint(Path("missing.jpg"))],
        AdaptiveCompressionProfile(target_entries=1, content_based_boundaries=True),
    )
    assert "limited_similarity_evidence" in missing[0].qualifications


def _closed_run(database: Path, source: Path) -> str:
    accounting = AccountingStore(database)
    accounting.register_dataset("dataset-a")
    run_id = accounting.start_or_resume_run("dataset-a", source)
    accounting.process_run(run_id)
    return run_id


class ColorEncoder:
    identity = "local-color-test-model@sha256:one"

    def encode_image(self, image_path: Path) -> tuple[float, ...]:
        with Image.open(image_path) as image:
            red, green, blue = ImageStat.Stat(image.convert("RGB")).mean
        return red / 255, green / 255, blue / 255


def _prepare_inputs(
    database: Path, source: Path, run_id: str
) -> tuple[CompressionInput, ...]:
    rendition_producer = ImageRenditionProducer(database)
    embedding_producer = EmbeddingProducer(database, ColorEncoder())
    profile = EmbeddingProfile(name="color-test", dimensions=3)
    inputs = []
    for path in sorted(source.iterdir()):
        relative = Path(path.name)
        rendition = rendition_producer.produce(run_id, relative)
        embedding = embedding_producer.produce(
            run_id, rendition.work.work_id, profile=profile
        )
        inputs.append(
            CompressionInput(
                relative_path=relative,
                visual_work_id=rendition.work.work_id,
                embedding_work_id=embedding.work.work_id,
            )
        )
    return tuple(inputs)


def test_adaptive_compression_reuses_inputs_across_different_result_targets(
    tmp_path: Path,
) -> None:
    database = tmp_path / "workspace" / "working.sqlite3"
    source = tmp_path / "source"
    source.mkdir()
    colors = ("red", "maroon", "green", "lime", "blue", "navy")
    for index, color in enumerate(colors):
        Image.new("RGB", (24, 24), color).save(source / f"item-{index}.jpg")
    source_before = {path.name: path.read_bytes() for path in source.iterdir()}
    first_run = _closed_run(database, source)
    first_inputs = _prepare_inputs(database, source, first_run)
    producer = AdaptiveCompressionProducer(database)

    two = producer.produce(
        first_run,
        first_inputs,
        profile=AdaptiveCompressionProfile(target_entries=2),
    )
    three = producer.produce(
        first_run,
        first_inputs,
        profile=AdaptiveCompressionProfile(target_entries=3),
    )

    assert len(two) == 2
    assert len(three) == 3
    assert all(outcome.work.status is WorkStatus.SUCCEEDED for outcome in two + three)
    assert {path for outcome in two for path in outcome.group.members} == {
        item.relative_path for item in first_inputs
    }
    assert not (
        {outcome.work.work_id for outcome in two}
        & {outcome.work.work_id for outcome in three}
    )

    results = ResultStore(database)
    two_result = results.seal(
        results.build_minimal(
            first_run,
            [item.visual_work_id for item in first_inputs],
            compression_work_ids=[outcome.work.work_id for outcome in two],
        )
    )
    two_result_bytes = two_result.path.read_bytes()
    three_result = results.seal(
        results.build_minimal(
            first_run,
            [item.visual_work_id for item in first_inputs],
            compression_work_ids=[outcome.work.work_id for outcome in three],
        )
    )
    reader = PrecheckReadTool(database)
    two_entries = reader.read(
        {
            "dataset_ref": "dataset:dataset-a",
            "action": "review",
            "result_ref": two_result.result_ref,
        }
    )
    three_entries = reader.read(
        {
            "dataset_ref": "dataset:dataset-a",
            "action": "review",
            "result_ref": three_result.result_ref,
        }
    )
    represented = set()
    for entry in two_entries["items"]:
        coverage = reader.read(
            {
                "dataset_ref": "dataset:dataset-a",
                "action": "resolve",
                "result_ref": two_result.result_ref,
                "source_set": entry["represents"]["source_set"],
            }
        )
        represented.update(item["source_item_ref"] for item in coverage["members"])
    first_entry_ref = two_entries["items"][0]["evidence_ref"]
    expanded = reader.read(
        {
            "dataset_ref": "dataset:dataset-a",
            "action": "expand",
            "result_ref": two_result.result_ref,
            "evidence_refs": [first_entry_ref],
            "include": ["anchor_evidence", "prepared_targets"],
        }
    )
    included = expanded["items"][0]["included"]
    first_entry = included["anchor_evidence"]

    assert len(two_entries["items"]) == 2
    assert len(three_entries["items"]) == 3
    assert len(represented) == 6
    assert any(
        observation["name"] == "evidence_role"
        and observation["value"]["role"] == "representative"
        for observation in first_entry["observations"]
    )
    assert any(
        item["target"]["kind"] == "evidence" for item in included["prepared_targets"]
    )
    assert two_result.result_ref != three_result.result_ref
    assert two_result.path.read_bytes() == two_result_bytes
    comparison = results.compare(two_result.result_ref, three_result.result_ref)
    assert comparison["left"]["entry_evidence"] == 2
    assert comparison["right"]["entry_evidence"] == 3
    assert comparison["source_boundary"]["same"] is True
    assert comparison["shared_artifact_count"] == 6

    second_run = _closed_run(database, source)
    second_inputs = _prepare_inputs(database, source, second_run)
    reused = producer.produce(
        second_run,
        second_inputs,
        profile=AdaptiveCompressionProfile(target_entries=2),
    )

    assert [outcome.work.work_id for outcome in reused] == [
        outcome.work.work_id for outcome in two
    ]
    assert all(outcome.reused for outcome in reused)
    assert {path.name: path.read_bytes() for path in source.iterdir()} == source_before


def test_bundle_members_are_covered_by_one_compressed_representative(
    tmp_path: Path,
) -> None:
    database = tmp_path / "workspace" / "working.sqlite3"
    source = tmp_path / "source"
    source.mkdir()
    Image.new("RGB", (24, 24), "red").save(source / "IMG_0001.JPG")
    (source / "IMG_0001.ARW").write_bytes(b"raw source bytes")
    run_id = _closed_run(database, source)
    bundle = next(BundleCandidateProducer(database).produce(run_id))
    assert bundle.candidate is not None
    rendition = ImageRenditionProducer(database).produce(run_id, Path("IMG_0001.JPG"))
    embedding = EmbeddingProducer(database, ColorEncoder()).produce(
        run_id,
        rendition.work.work_id,
        profile=EmbeddingProfile(name="color-test", dimensions=3),
    )
    compression = AdaptiveCompressionProducer(database).produce(
        run_id,
        (
            CompressionInput(
                relative_path=Path("IMG_0001.JPG"),
                visual_work_id=rendition.work.work_id,
                member_paths=bundle.candidate.members,
                bundle_work_id=bundle.work.work_id,
                embedding_work_id=embedding.work.work_id,
            ),
        ),
        profile=AdaptiveCompressionProfile(target_entries=1),
    )
    store = ResultStore(database)
    sealed = store.seal(
        store.build_minimal(
            run_id,
            [rendition.work.work_id],
            compression_work_ids=[compression[0].work.work_id],
        )
    )
    reader = PrecheckReadTool(database)
    accounts = reader.read(
        {
            "dataset_ref": "dataset:dataset-a",
            "action": "resolve",
            "result_ref": sealed.result_ref,
            "source_set": {
                "kind": "precheck_relation",
                "origin": sealed.result_ref,
                "relation": "accounts_for",
                "direction": "outbound",
            },
        }
    )
    raw_account = next(
        item
        for item in accounts["members"]
        if item["locator"]["value"] == "IMG_0001.ARW"
    )
    raw_ref = raw_account["source_item_ref"]
    reverse = reader.read(
        {
            "dataset_ref": "dataset:dataset-a",
            "action": "expand",
            "result_ref": sealed.result_ref,
            "source_item_refs": [raw_ref],
            "include": ["covering_evidence"],
        }
    )
    result_view = reader.read(
        {
            "dataset_ref": "dataset:dataset-a",
            "action": "review",
            "result_ref": sealed.result_ref,
        }
    )["result"]
    covering = reverse["items"][0]["included"]["covering_evidence"]
    assert len(covering) == 1
    assert covering[0]["qualifications"] == [
        {
            "code": "limited_similarity_evidence",
            "effect": "limits_interpretation",
            "message": "This compression claim has incomplete comparison evidence.",
        },
        {
            "code": "bundle_members_not_visually_compared",
            "effect": "limits_interpretation",
            "message": "This compression claim has incomplete comparison evidence.",
        },
    ]
    assert raw_account["condition"] == "usable"
    assert result_view["readiness"] == "plan_ready"


def test_large_embedding_group_uses_bounded_representative_selection() -> None:
    points = tuple(
        CompressionPoint(
            Path(f"item-{index:04d}.jpg"),
            embedding=(1.0, index / 1000),
        )
        for index in range(1_000)
    )
    profile = AdaptiveCompressionProfile(
        target_entries=1,
        exact_representative_limit=16,
        representative_comparison_budget=256,
    )

    group = build_adaptive_groups(points, profile)[0]

    assert group.basis["representative_method"] == "bounded-even-sample-v1"
    assert group.basis["representative_comparison_count"] <= 256
    assert "bounded_representative_selection" in group.qualifications
