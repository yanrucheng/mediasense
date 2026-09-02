from __future__ import annotations

from pathlib import Path
import sys
from types import SimpleNamespace

from PIL import Image
import pytest

from mediasense.precheck import (
    AccountingStore,
    ChineseCLIPEncoder,
    EmbeddingProducer,
    EmbeddingProfile,
    HIGH_RESOLUTION_RENDITION_PROFILE,
    ImageRenditionProducer,
    WorkStatus,
    cosine_similarity,
    read_embedding,
)


def _closed_run(database: Path, source: Path) -> str:
    accounting = AccountingStore(database)
    accounting.register_dataset("dataset-a")
    run_id = accounting.start_or_resume_run("dataset-a", source)
    accounting.process_run(run_id)
    return run_id


class FakeEncoder:
    def __init__(self, identity: str = "fake-local-model@sha256:one") -> None:
        self.identity = identity
        self.calls: list[Path] = []

    def encode_image(self, image_path: Path) -> tuple[float, ...]:
        self.calls.append(image_path)
        with Image.open(image_path) as image:
            width, height = image.size
        return (float(width), float(height), 1.0, 2.0)


class BatchEncoder(FakeEncoder):
    def __init__(self) -> None:
        super().__init__()
        self.batch_calls: list[tuple[Path, ...]] = []

    def encode_images(
        self, image_paths: tuple[Path, ...]
    ) -> tuple[tuple[float, ...], ...]:
        self.batch_calls.append(image_paths)
        return tuple(self.encode_image(path) for path in image_paths)


class FakeTensor:
    def to(self, _device: str) -> FakeTensor:
        return self

    def detach(self) -> FakeTensor:
        return self

    def cpu(self) -> FakeTensor:
        return self

    def flatten(self) -> FakeTensor:
        return self

    def tolist(self) -> list[float]:
        return [1.0, 2.0, 3.0, 4.0]


def test_embedding_is_an_immutable_artifact_reused_across_runs(tmp_path: Path) -> None:
    database = tmp_path / "workspace" / "working.sqlite3"
    source = tmp_path / "source"
    source.mkdir()
    image_path = source / "photo.jpg"
    Image.new("RGB", (80, 40), "blue").save(image_path)
    source_before = image_path.read_bytes()
    profile = EmbeddingProfile(name="test-vector", dimensions=4)
    encoder = FakeEncoder()

    first_run = _closed_run(database, source)
    first_rendition = ImageRenditionProducer(database).produce(
        first_run,
        Path("photo.jpg"),
        profile=HIGH_RESOLUTION_RENDITION_PROFILE,
    )
    first = EmbeddingProducer(database, encoder).produce(
        first_run, first_rendition.work.work_id, profile=profile
    )

    assert first.work.status is WorkStatus.SUCCEEDED
    assert first.artifact is not None
    assert first.artifact.media_type == "application/vnd.mediasense.embedding-f32le"
    assert read_embedding(first.artifact, profile) == (80.0, 40.0, 1.0, 2.0)
    assert cosine_similarity(
        read_embedding(first.artifact, profile),
        read_embedding(first.artifact, profile),
    ) == pytest.approx(1.0)
    assert image_path.read_bytes() == source_before

    second_run = _closed_run(database, source)
    reused_rendition = ImageRenditionProducer(database).produce(
        second_run,
        Path("photo.jpg"),
        profile=HIGH_RESOLUTION_RENDITION_PROFILE,
    )
    reused = EmbeddingProducer(database, encoder).produce(
        second_run, reused_rendition.work.work_id, profile=profile
    )

    assert reused.work.work_id == first.work.work_id
    assert reused.artifact == first.artifact
    assert reused.reused is True
    assert len(encoder.calls) == 1


def test_embedding_many_uses_one_backend_batch_with_per_item_work(
    tmp_path: Path,
) -> None:
    database = tmp_path / "workspace" / "working.sqlite3"
    source = tmp_path / "source"
    source.mkdir()
    for name, color in (("a.jpg", "red"), ("b.jpg", "blue")):
        Image.new("RGB", (80, 40), color).save(source / name)
    run_id = _closed_run(database, source)
    renditions = tuple(
        ImageRenditionProducer(database).produce(
            run_id,
            Path(name),
            profile=HIGH_RESOLUTION_RENDITION_PROFILE,
        )
        for name in ("a.jpg", "b.jpg")
    )
    encoder = BatchEncoder()

    outcomes = EmbeddingProducer(database, encoder).produce_many(
        run_id,
        tuple(outcome.work.work_id for outcome in renditions),
        profile=EmbeddingProfile(name="test-vector", dimensions=4),
    )

    assert len(encoder.batch_calls) == 1
    assert len(encoder.batch_calls[0]) == 2
    assert len(outcomes) == 2
    assert all(
        outcome.work.status is WorkStatus.SUCCEEDED for outcome in outcomes.values()
    )


def test_embedding_model_identity_and_integrity_control_reuse(tmp_path: Path) -> None:
    database = tmp_path / "workspace" / "working.sqlite3"
    source = tmp_path / "source"
    source.mkdir()
    Image.new("RGB", (48, 32), "green").save(source / "photo.jpg")
    profile = EmbeddingProfile(name="test-vector", dimensions=4)
    run_id = _closed_run(database, source)
    rendition = ImageRenditionProducer(database).produce(
        run_id,
        Path("photo.jpg"),
        profile=HIGH_RESOLUTION_RENDITION_PROFILE,
    )
    first_encoder = FakeEncoder("fake-local-model@sha256:one")
    first = EmbeddingProducer(database, first_encoder).produce(
        run_id, rendition.work.work_id, profile=profile
    )
    assert first.artifact is not None

    changed_model = EmbeddingProducer(
        database, FakeEncoder("fake-local-model@sha256:two")
    ).produce(run_id, rendition.work.work_id, profile=profile)
    assert changed_model.work.work_id != first.work.work_id

    first.artifact.path.chmod(0o644)
    first.artifact.path.write_bytes(b"corrupt")
    replacement = EmbeddingProducer(database, first_encoder).produce(
        run_id, rendition.work.work_id, profile=profile
    )

    assert replacement.work.status is WorkStatus.SUCCEEDED
    assert replacement.work.work_id != first.work.work_id
    assert replacement.artifact is not None
    assert read_embedding(replacement.artifact, profile) == (48.0, 32.0, 1.0, 2.0)


def test_invalid_embedding_is_a_local_terminal_failure(tmp_path: Path) -> None:
    database = tmp_path / "workspace" / "working.sqlite3"
    source = tmp_path / "source"
    source.mkdir()
    Image.new("RGB", (20, 20), "red").save(source / "photo.jpg")
    run_id = _closed_run(database, source)
    rendition = ImageRenditionProducer(database).produce(
        run_id, Path("photo.jpg"), profile=HIGH_RESOLUTION_RENDITION_PROFILE
    )

    outcome = EmbeddingProducer(database, FakeEncoder()).produce(
        run_id,
        rendition.work.work_id,
        profile=EmbeddingProfile(name="wrong-shape", dimensions=3),
    )

    assert outcome.work.status is WorkStatus.TERMINAL_FAILURE
    assert outcome.work.last_failure_code == "embedding_failed"
    assert outcome.artifact is None


def test_chinese_clip_adapter_requires_pinned_local_model_files(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    calls: list[tuple[str, dict[str, object]]] = []

    class FakeModel:
        @classmethod
        def from_pretrained(cls, model_id: str, **kwargs: object) -> FakeModel:
            calls.append((f"model:{model_id}", kwargs))
            return cls()

        def to(self, _device: str) -> FakeModel:
            return self

        def eval(self) -> None:
            return None

        def get_image_features(self, **_inputs: object) -> FakeTensor:
            return FakeTensor()

    class FakeProcessor:
        @classmethod
        def from_pretrained(cls, model_id: str, **kwargs: object) -> FakeProcessor:
            calls.append((f"processor:{model_id}", kwargs))
            return cls()

        def __call__(self, **_inputs: object) -> dict[str, FakeTensor]:
            return {"pixel_values": FakeTensor()}

    class NoGrad:
        def __enter__(self) -> None:
            return None

        def __exit__(self, *_args: object) -> None:
            return None

    monkeypatch.setitem(
        sys.modules,
        "transformers",
        SimpleNamespace(
            ChineseCLIPModel=FakeModel,
            ChineseCLIPProcessor=FakeProcessor,
        ),
    )
    monkeypatch.setitem(sys.modules, "torch", SimpleNamespace(no_grad=NoGrad))
    image = tmp_path / "input.jpg"
    Image.new("RGB", (8, 8), "white").save(image)

    values = ChineseCLIPEncoder(revision="model-commit").encode_image(image)

    assert values == (1.0, 2.0, 3.0, 4.0)
    assert len(calls) == 2
    assert all(call[1]["revision"] == "model-commit" for call in calls)
    assert all(call[1]["local_files_only"] is True for call in calls)
