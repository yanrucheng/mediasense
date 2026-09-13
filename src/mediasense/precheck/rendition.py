"""Conservative local still-image rendition producer for PreCheck Slice 1."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import timedelta
import os
from pathlib import Path
import warnings

from PIL import Image, ImageOps, UnidentifiedImageError, __version__, features

from ._artifact_types import (
    ArtifactIntegrityError,
    ArtifactRecord,
    InvalidArtifactDraft,
)
from ._fingerprint import SourceChangedDuringRead
from ._work_types import (
    DependencyKind,
    LeaseLost,
    WorkDependency,
    WorkRecord,
    WorkSpec,
    WorkStatus,
    source_revision_dependency,
)
from .artifact import ArtifactStore
from .source_validity import SourceValidityStore
from .work import WorkStore

PRODUCER_IDENTITY = "builtin-image-rendition-v1"


@dataclass(frozen=True, slots=True)
class RenditionProfile:
    name: str = "ordinary"
    max_edge: int = 640
    jpeg_quality: int = 85

    def __post_init__(self) -> None:
        if self.name not in {"ordinary", "high_resolution", "custom"}:
            raise ValueError("unknown rendition profile name")
        if self.max_edge < 1:
            raise ValueError("rendition max_edge must be positive")
        if not 1 <= self.jpeg_quality <= 95:
            raise ValueError("rendition jpeg_quality must be between 1 and 95")


@dataclass(frozen=True, slots=True)
class RenditionOutcome:
    work: WorkRecord
    artifact: ArtifactRecord | None
    reused: bool


class ImageRenditionProducer:
    """Produce one local JPEG Artifact without changing the source file."""

    def __init__(self, database_path: Path) -> None:
        self.database_path = Path(database_path)
        self.validity = SourceValidityStore(self.database_path)
        self.work = WorkStore(self.database_path)
        self.artifacts = ArtifactStore(self.database_path)

    def produce(
        self,
        run_id: str,
        relative_path: Path,
        *,
        profile: RenditionProfile = RenditionProfile(),
        owner: str = "builtin-image-rendition",
    ) -> RenditionOutcome:
        return self._produce(
            run_id, relative_path, profile=profile, owner=owner, render=_render_jpeg
        )

    def produce_profiles(
        self,
        run_id: str,
        relative_path: Path,
        *,
        profiles: tuple[RenditionProfile, ...],
    ) -> tuple[RenditionOutcome, ...]:
        """Keep independent Work while sharing one lazily decoded source per call."""
        from ._sqlite_scope import connection_scope

        with connection_scope(self.database_path):
            return self._produce_profiles(run_id, relative_path, profiles=profiles)

    def _produce_profiles(self, run_id, relative_path, *, profiles):
        decoded = None
        identity = None

        def render(source_path, destination, profile):
            nonlocal decoded, identity
            current = source_path.stat()
            stamp = (
                current.st_dev,
                current.st_ino,
                current.st_size,
                current.st_mtime_ns,
                current.st_ctime_ns,
            )
            if decoded is None or stamp != identity:
                if decoded is not None:
                    decoded.close()
                decoded = _decode_rgb(source_path)
                identity = stamp
            return _write_jpeg(decoded, destination, profile)

        try:
            return tuple(
                self._produce(
                    run_id,
                    relative_path,
                    profile=profile,
                    owner="builtin-image-rendition",
                    render=render,
                )
                for profile in profiles
            )
        finally:
            if decoded is not None:
                decoded.close()

    def _produce(self, run_id, relative_path, *, profile, owner, render):
        proof = self.validity.prove(run_id, relative_path)
        spec = WorkSpec(
            capability="image-rendition",
            producer_identity=PRODUCER_IDENTITY,
            dependencies=(
                source_revision_dependency(
                    proof.dataset_id, proof.relative_path, proof.source_revision
                ),
                proof.dependency(),
                WorkDependency(
                    DependencyKind.PARAMETER,
                    "profile_name",
                    profile.name,
                ),
                WorkDependency(
                    DependencyKind.PARAMETER,
                    "max_edge",
                    str(profile.max_edge),
                ),
                WorkDependency(
                    DependencyKind.PARAMETER,
                    "jpeg_quality",
                    str(profile.jpeg_quality),
                ),
                WorkDependency(
                    DependencyKind.PARAMETER,
                    "orientation_policy",
                    "exif-transpose-v1",
                ),
                WorkDependency(
                    DependencyKind.ENVIRONMENT,
                    "pillow_version",
                    __version__,
                ),
                WorkDependency(
                    DependencyKind.ENVIRONMENT,
                    "jpeg_codec_version",
                    features.version_codec("jpg") or "unknown",
                ),
            ),
        )
        record = self.work.ensure_work(run_id, spec)
        if record.status is WorkStatus.SUCCEEDED:
            artifacts = self.artifacts.artifacts_for_work(record.work_id)
            if artifacts and all(
                artifact.integrity.value == "available" for artifact in artifacts
            ):
                return RenditionOutcome(record, artifacts[0], True)
            record = self.work.ensure_work(run_id, spec)
        if record.status not in {WorkStatus.READY, WorkStatus.RETRYABLE_FAILURE}:
            return RenditionOutcome(record, None, False)

        leases = self.work.claim_ready_work(
            run_id,
            owner,
            lease_duration=timedelta(minutes=5),
            work_id=record.work_id,
        )
        if not leases:
            return RenditionOutcome(self.work.get_work(record.work_id), None, False)
        lease = leases[0]
        draft = self.artifacts.create_draft(lease, suffix=".jpg")
        try:
            width, height = render(proof.source_path, draft.path, profile)
            self.validity.verify(run_id, proof)
        except (
            UnidentifiedImageError,
            Image.DecompressionBombError,
            Image.DecompressionBombWarning,
            OSError,
            ValueError,
        ) as error:
            draft.path.unlink(missing_ok=True)
            failed = self.work.fail_work(
                lease,
                error_code="image_decode_failed",
                message=str(error) or type(error).__name__,
                retryable=False,
            )
            return RenditionOutcome(failed, None, False)
        try:
            completed, artifact = self.artifacts.publish(
                lease,
                draft,
                suffix=".jpg",
                media_type="image/jpeg",
                role="rendition",
                output={
                    "format": "jpeg",
                    "height": height,
                    "profile": {
                        "jpeg_quality": profile.jpeg_quality,
                        "max_edge": profile.max_edge,
                        "name": profile.name,
                        "orientation": "exif-transpose-v1",
                    },
                    "width": width,
                },
            )
            return RenditionOutcome(completed, artifact, False)
        except SourceChangedDuringRead:
            draft.path.unlink(missing_ok=True)
            self.work.invalidate_work(
                record.work_id,
                "source changed before Artifact publication",
            )
            return RenditionOutcome(self.work.get_work(record.work_id), None, False)
        except (
            ArtifactIntegrityError,
            InvalidArtifactDraft,
            OSError,
            ValueError,
        ) as error:
            draft.path.unlink(missing_ok=True)
            try:
                failed = self.work.fail_work(
                    lease,
                    error_code="artifact_publish_failed",
                    message=str(error) or type(error).__name__,
                    retryable=True,
                )
            except LeaseLost:
                failed = self.work.get_work(record.work_id)
            return RenditionOutcome(failed, None, False)


def _render_jpeg(
    source_path: Path,
    destination: Path,
    profile: RenditionProfile,
) -> tuple[int, int]:
    with _decode_rgb(source_path) as decoded:
        return _write_jpeg(decoded, destination, profile)


def _decode_rgb(source_path):
    with warnings.catch_warnings():
        warnings.simplefilter("error", Image.DecompressionBombWarning)
        with Image.open(source_path) as opened:
            opened.load()
            with ImageOps.exif_transpose(opened) as oriented:
                return _as_rgb(oriented)


def _write_jpeg(decoded, destination, profile):
    with decoded.copy() as rendered:
        rendered.thumbnail(
            (profile.max_edge, profile.max_edge),
            Image.Resampling.LANCZOS,
            reducing_gap=3.0,
        )
        width, height = rendered.size
        with destination.open("wb") as output:
            rendered.save(
                output, format="JPEG", quality=profile.jpeg_quality, optimize=True
            )
            output.flush()
            os.fsync(output.fileno())
    with Image.open(destination) as verification:
        verification.verify()
    return width, height


def _as_rgb(image: Image.Image) -> Image.Image:
    if image.mode == "RGB":
        return image.copy()
    if image.mode in {"RGBA", "LA"} or "transparency" in image.info:
        rgba = image.convert("RGBA")
        background = Image.new("RGB", rgba.size, "white")
        background.paste(rgba, mask=rgba.getchannel("A"))
        return background
    return image.convert("RGB")


ORDINARY_RENDITION_PROFILE = RenditionProfile()
HIGH_RESOLUTION_RENDITION_PROFILE = RenditionProfile(
    name="high_resolution",
    max_edge=1920,
    jpeg_quality=90,
)


__all__ = [
    "HIGH_RESOLUTION_RENDITION_PROFILE",
    "ImageRenditionProducer",
    "ORDINARY_RENDITION_PROFILE",
    "RenditionOutcome",
    "RenditionProfile",
]
