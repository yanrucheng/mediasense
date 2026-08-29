from __future__ import annotations

from pathlib import Path

from PIL import Image, ImageStat

from mediasense.precheck import (
    AccountingStore,
    AdaptiveCompressionProducer,
    AdaptiveCompressionProfile,
    BundleCandidateProducer,
    CompressionInput,
    EmbeddingProducer,
    EmbeddingProfile,
    ImageRenditionProducer,
    PrecheckReadTool,
    ResultStore,
    WorkStatus,
)


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
            "action": "traverse",
            "direction": "outbound",
            "relation": "entry_evidence",
            "result_ref": two_result.result_ref,
        }
    )
    three_entries = reader.read(
        {
            "action": "traverse",
            "direction": "outbound",
            "relation": "entry_evidence",
            "result_ref": three_result.result_ref,
        }
    )
    represented = set()
    for entry in two_entries["items"]:
        coverage = reader.read(
            {
                "action": "traverse",
                "direction": "outbound",
                "relation": "represents",
                "result_ref": two_result.result_ref,
                "target": entry["target"],
            }
        )
        represented.update(item["target"] for item in coverage["items"])
    first_entry_ref = two_entries["items"][0]["target"]
    first_entry = reader.read(
        {
            "action": "inspect",
            "result_ref": two_result.result_ref,
            "target": {"kind": "evidence", "ref": first_entry_ref},
        }
    )["target"]
    expanded = reader.read(
        {
            "action": "traverse",
            "direction": "outbound",
            "relation": "expands_to",
            "result_ref": two_result.result_ref,
            "target": first_entry_ref,
        }
    )

    assert len(two_entries["items"]) == 2
    assert len(three_entries["items"]) == 3
    assert len(represented) == 6
    assert any(
        observation["name"] == "evidence_role"
        and observation["value"]["role"] == "representative"
        for observation in first_entry["observations"]
    )
    assert any(item["target"]["kind"] == "evidence" for item in expanded["items"])
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
    bundle = BundleCandidateProducer(database).produce(run_id)[0]
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
            "action": "traverse",
            "direction": "outbound",
            "relation": "accounts_for",
            "result_ref": sealed.result_ref,
        }
    )
    raw_ref = next(
        item["target"]
        for item in accounts["items"]
        if reader.read(
            {
                "action": "inspect",
                "result_ref": sealed.result_ref,
                "target": {"kind": "source_item", "ref": item["target"]},
            }
        )["target"]["locator"]["value"]
        == "IMG_0001.ARW"
    )
    reverse = reader.read(
        {
            "action": "traverse",
            "direction": "inbound",
            "relation": "represents",
            "result_ref": sealed.result_ref,
            "target": raw_ref,
        }
    )

    assert len(reverse["items"]) == 1
