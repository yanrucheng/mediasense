"""Pure adaptive-compression value types and selection strategy."""

from __future__ import annotations

from collections.abc import Sequence
from bisect import bisect_left
from dataclasses import dataclass
from datetime import datetime, timezone
import hashlib
import json
import math
from pathlib import Path

from .embedding import cosine_similarity


_REPRESENTATIVE_EXTENSIONS = (".jpg", ".jpeg", ".heic", ".png", ".mov", ".mp4")


@dataclass(frozen=True, slots=True)
class AdaptiveCompressionProfile:
    target_entries: int
    temporal_scale_seconds: float = 86_400.0
    spatial_scale_meters: float = 3_000.0
    content_distance_scale: float = 0.311
    representative_top_k: float = 0.5
    exact_representative_limit: int = 256
    representative_comparison_budget: int = 65_536
    content_based_boundaries: bool = False

    def __post_init__(self) -> None:
        if self.target_entries < 1:
            raise ValueError("compression target entries must be positive")
        if self.temporal_scale_seconds <= 0 or self.spatial_scale_meters <= 0:
            raise ValueError("compression distance scales must be positive")
        if self.content_distance_scale <= 0:
            raise ValueError("content distance scale must be positive")
        if not 0 < self.representative_top_k <= 1:
            raise ValueError("representative_top_k must be in (0, 1]")
        if self.exact_representative_limit < 2:
            raise ValueError("exact representative limit must be at least two")
        if self.representative_comparison_budget < 1:
            raise ValueError("representative comparison budget must be positive")


@dataclass(frozen=True, slots=True)
class CompressionPoint:
    relative_path: Path
    capture_time: datetime | None = None
    gps: tuple[float, float] | None = None
    embedding: tuple[float, ...] | None = None
    members: tuple[Path, ...] = ()
    weight: int = 1

    def __post_init__(self) -> None:
        path = _relative_path(self.relative_path)
        members = self.members or (path,)
        members = tuple(sorted({_relative_path(member) for member in members}))
        if path not in members:
            raise ValueError(
                "compression point members must include its representative"
            )
        if self.capture_time is not None and (
            self.capture_time.tzinfo is None or self.capture_time.utcoffset() is None
        ):
            raise ValueError("compression capture time must be timezone-aware")
        if self.gps is not None:
            latitude, longitude = self.gps
            if not -90 <= latitude <= 90 or not -180 <= longitude <= 180:
                raise ValueError("compression coordinates are out of range")
        if self.embedding is not None:
            embedding = tuple(float(value) for value in self.embedding)
            if not embedding or not all(math.isfinite(value) for value in embedding):
                raise ValueError("compression embedding must be finite and non-empty")
            if not any(value != 0 for value in embedding):
                raise ValueError("compression embedding must not be a zero vector")
            object.__setattr__(self, "embedding", embedding)
        if self.weight < 1:
            raise ValueError("compression point weight must be positive")
        object.__setattr__(self, "relative_path", path)
        object.__setattr__(self, "members", members)


@dataclass(frozen=True, slots=True)
class CompressionGroup:
    group_id: str
    members: tuple[Path, ...]
    representative_path: Path
    boundary_paths: tuple[Path, ...]
    outlier_paths: tuple[Path, ...]
    conflict_paths: tuple[Path, ...]
    qualifications: tuple[str, ...]
    basis: dict[str, object]


def build_adaptive_groups(
    points: Sequence[CompressionPoint],
    profile: AdaptiveCompressionProfile,
) -> tuple[CompressionGroup, ...]:
    ordered = tuple(
        sorted(
            points,
            key=lambda item: (
                item.capture_time is None,
                item.capture_time or datetime.max.replace(tzinfo=timezone.utc),
                item.relative_path.as_posix(),
            ),
        )
    )
    if len({path for point in ordered for path in point.members}) != sum(
        len(point.members) for point in ordered
    ):
        raise ValueError("compression point memberships must not overlap")
    if not ordered:
        return ()
    target = min(profile.target_entries, len(ordered))
    boundaries = [
        _boundary_strength(left, right, profile)
        for left, right in zip(ordered, ordered[1:], strict=False)
    ]
    ideal_cuts = tuple(
        round(index * len(ordered) / target) for index in range(1, target)
    )
    def nearest_cut_distance(position):
        index = bisect_left(ideal_cuts, position)
        return min((abs(position - cut) for cut in ideal_cuts[max(0, index - 1):index + 1]), default=0)

    selected_cuts = {
        index
        for index, _score in sorted(
            enumerate(boundaries, start=1),
            key=lambda item: (
                item[1]["score"],
                -nearest_cut_distance(item[0]),
                -item[0],
            ),
            reverse=True,
        )[: target - 1]
    }
    if profile.content_based_boundaries:
        # Missing comparisons retain the bounded fallback. Available content can
        # collapse redundant entries, but a strong discontinuity always survives
        # the count budget. Anchor comparison prevents gradual adjacent drift.
        fallback_cuts = selected_cuts
        selected_cuts = set()
        anchor = ordered[0]
        for index, boundary in enumerate(boundaries, 1):
            right = ordered[index]
            left = ordered[index - 1]
            missing = (
                left.embedding is None
                or right.embedding is None
                or anchor.embedding is None
            )
            discontinuity = any(
                boundary[key] >= 1
                for key in (
                    "date_change",
                    "time_distance",
                    "spatial_distance",
                    "content_distance",
                )
            )
            drift = (
                not missing
                and (1 - cosine_similarity(anchor.embedding, right.embedding))
                >= profile.content_distance_scale
            )
            if discontinuity or drift or (missing and index in fallback_cuts):
                selected_cuts.add(index)
                anchor = right
    partitions: list[tuple[CompressionPoint, ...]] = []
    start = 0
    for index in range(1, len(ordered)):
        if index in selected_cuts:
            partitions.append(ordered[start:index])
            start = index
    partitions.append(ordered[start:])
    groups = [
        _compression_group(
            partition,
            profile,
            left_boundary=(None if index == 0 else boundaries[start_index - 1]),
            right_boundary=(
                None
                if index == len(partitions) - 1
                else boundaries[start_index + len(partition) - 1]
            ),
        )
        for index, (partition, start_index) in enumerate(
            _partitions_with_offsets(partitions)
        )
    ]
    return tuple(groups)


def select_embedding_representative(
    embeddings: Sequence[Sequence[float]],
    *,
    top_k: int | float = 0.5,
    max_comparisons: int = 65_536,
) -> int:
    selected, _method, _comparisons = _bounded_embedding_representative(
        embeddings,
        top_k=top_k,
        exact_limit=max(2, len(embeddings)),
        comparison_budget=max_comparisons,
    )
    return selected


def _bounded_embedding_representative(
    embeddings: Sequence[Sequence[float]],
    *,
    top_k: int | float,
    exact_limit: int,
    comparison_budget: int,
) -> tuple[int, str, int]:
    if not embeddings:
        raise ValueError("representative selection requires embeddings")
    dimensions = {len(vector) for vector in embeddings}
    if len(dimensions) != 1 or 0 in dimensions:
        raise ValueError("representative embeddings must share non-zero dimensions")
    if comparison_budget < 1:
        raise ValueError("representative comparison budget must be positive")
    if isinstance(top_k, float):
        if not 0 < top_k <= 1:
            raise ValueError("floating top_k must be in (0, 1]")
        count = max(int(round(len(embeddings) * top_k)), 2)
    else:
        if top_k < 1:
            raise ValueError("integer top_k must be positive")
        count = top_k
    exact_comparisons = len(embeddings) * max(0, len(embeddings) - 1)
    if len(embeddings) <= exact_limit and exact_comparisons <= comparison_budget:
        candidates = tuple(range(len(embeddings)))
        peers = candidates
        method = "exact-all-pairs-v1"
    else:
        side = max(1, int(math.sqrt(comparison_budget)))
        candidate_count = min(len(embeddings), exact_limit, side)
        peer_count = min(
            len(embeddings),
            max(1, comparison_budget // max(1, candidate_count)),
        )
        candidates = _evenly_spaced_indices(len(embeddings), candidate_count)
        peers = _evenly_spaced_indices(len(embeddings), peer_count)
        method = "bounded-even-sample-v1"
    best_index = candidates[0]
    best_average = 0.0
    comparisons = 0
    for index in candidates:
        vector = embeddings[index]
        similarities = sorted(
            (
                cosine_similarity(vector, embeddings[other_index])
                for other_index in peers
                if index != other_index
            ),
            reverse=True,
        )[:count]
        comparisons += len(peers) - int(index in peers)
        average = sum(similarities) / len(similarities) if similarities else 0.0
        if average > best_average:
            best_average = average
            best_index = index
    return best_index, method, comparisons


def _evenly_spaced_indices(length: int, count: int) -> tuple[int, ...]:
    if count >= length:
        return tuple(range(length))
    if count == 1:
        return (0,)
    return tuple((index * (length - 1)) // (count - 1) for index in range(count))


def _compression_group(
    points: tuple[CompressionPoint, ...],
    profile: AdaptiveCompressionProfile,
    *,
    left_boundary: dict[str, float] | None,
    right_boundary: dict[str, float] | None,
) -> CompressionGroup:
    embedded = tuple(point for point in points if point.embedding is not None)
    if embedded:
        selected, representative_method, comparison_count = (
            _bounded_embedding_representative(
                tuple(
                    point.embedding for point in embedded if point.embedding is not None
                ),
                top_k=profile.representative_top_k,
                exact_limit=profile.exact_representative_limit,
                comparison_budget=profile.representative_comparison_budget,
            )
        )
        representative = embedded[selected]
    else:
        representative_method = "extension-priority-v1"
        comparison_count = 0
        representative = min(
            points,
            key=lambda item: (
                _extension_rank(item.relative_path),
                item.relative_path.as_posix(),
            ),
        )
    outliers: tuple[Path, ...] = ()
    if representative.embedding is not None and len(embedded) > 1:
        farthest = min(
            (point for point in embedded if point is not representative),
            key=lambda point: (
                cosine_similarity(
                    representative.embedding or (), point.embedding or ()
                ),
                point.relative_path.as_posix(),
            ),
        )
        outliers = (farthest.relative_path,)
    members = tuple(sorted(path for point in points for path in point.members))
    boundary_paths = tuple(
        dict.fromkeys((points[0].relative_path, points[-1].relative_path))
    )
    qualifications = []
    if any(
        point.capture_time is None or point.gps is None or point.embedding is None
        for point in points
    ):
        qualifications.append("limited_similarity_evidence")
    if representative_method == "bounded-even-sample-v1":
        qualifications.append("bounded_representative_selection")
    if any(len(point.members) > 1 for point in points):
        qualifications.append("bundle_members_not_visually_compared")
    conflicts = _conflict_paths(points, profile)
    if conflicts:
        qualifications.append("candidate_axes_disagree")
    payload = [path.as_posix() for path in members]
    return CompressionGroup(
        group_id="compression-group:sha256:"
        + hashlib.sha256(
            json.dumps(payload, ensure_ascii=False, separators=(",", ":")).encode()
        ).hexdigest(),
        members=members,
        representative_path=representative.relative_path,
        boundary_paths=boundary_paths,
        outlier_paths=outliers,
        conflict_paths=conflicts,
        qualifications=tuple(qualifications),
        basis={
            "left_boundary": left_boundary,
            "method": "content-boundaries-with-anchor-v1"
            if profile.content_based_boundaries
            else "ranked-adjacent-boundaries-v1",
            "embedded_point_count": len(embedded),
            "candidate_point_count": len(points),
            "representative_comparison_budget": (
                profile.representative_comparison_budget
            ),
            "representative_comparison_count": comparison_count,
            "representative_method": representative_method,
            "requested_target_entries": profile.target_entries,
            "right_boundary": right_boundary,
        },
    )


def _boundary_strength(
    left: CompressionPoint,
    right: CompressionPoint,
    profile: AdaptiveCompressionProfile,
) -> dict[str, float]:
    date_change = 0.0
    time_distance = 0.0
    if left.capture_time is not None and right.capture_time is not None:
        date_change = float(left.capture_time.date() != right.capture_time.date())
        time_distance = (
            abs((right.capture_time - left.capture_time).total_seconds())
            / profile.temporal_scale_seconds
        )
    spatial_distance = (
        0.0
        if left.gps is None or right.gps is None
        else _haversine_meters(left.gps, right.gps) / profile.spatial_scale_meters
    )
    content_distance = (
        0.0
        if left.embedding is None or right.embedding is None
        else (1.0 - cosine_similarity(left.embedding, right.embedding))
        / profile.content_distance_scale
    )
    score = (
        date_change * 1_000.0
        + min(time_distance, 100.0) * 10.0
        + min(spatial_distance, 100.0) * 2.0
        + min(content_distance, 100.0)
    )
    return {
        "content_distance": content_distance,
        "date_change": date_change,
        "score": score,
        "spatial_distance": spatial_distance,
        "time_distance": time_distance,
    }


def _haversine_meters(left: tuple[float, float], right: tuple[float, float]) -> float:
    radius = 6_371_008.8
    lat1, lon1 = map(math.radians, left)
    lat2, lon2 = map(math.radians, right)
    delta_lat = lat2 - lat1
    delta_lon = lon2 - lon1
    value = (
        math.sin(delta_lat / 2) ** 2
        + math.cos(lat1) * math.cos(lat2) * math.sin(delta_lon / 2) ** 2
    )
    return radius * 2 * math.asin(min(1.0, math.sqrt(value)))


def _conflict_paths(
    points: tuple[CompressionPoint, ...],
    profile: AdaptiveCompressionProfile,
) -> tuple[Path, ...]:
    conflicts = []
    for left, right in zip(points, points[1:], strict=False):
        judgments = []
        if left.capture_time is not None and right.capture_time is not None:
            judgments.append(
                left.capture_time.date() != right.capture_time.date()
                or abs((right.capture_time - left.capture_time).total_seconds())
                >= profile.temporal_scale_seconds
            )
        if left.gps is not None and right.gps is not None:
            judgments.append(
                _haversine_meters(left.gps, right.gps) >= profile.spatial_scale_meters
            )
        if left.embedding is not None and right.embedding is not None:
            judgments.append(
                1.0 - cosine_similarity(left.embedding, right.embedding)
                >= profile.content_distance_scale
            )
        if judgments and any(judgments) and not all(judgments):
            conflicts.extend((left.relative_path, right.relative_path))
    return tuple(dict.fromkeys(conflicts))


def _partitions_with_offsets(
    partitions: Sequence[tuple[CompressionPoint, ...]],
) -> tuple[tuple[tuple[CompressionPoint, ...], int], ...]:
    offset = 0
    values = []
    for partition in partitions:
        values.append((partition, offset))
        offset += len(partition)
    return tuple(values)


def _extension_rank(path: Path) -> tuple[int, str]:
    try:
        rank = _REPRESENTATIVE_EXTENSIONS.index(path.suffix.casefold())
    except ValueError:
        rank = len(_REPRESENTATIVE_EXTENSIONS)
    return rank, path.as_posix()


def _relative_path(value: Path) -> Path:
    path = Path(value)
    if path.is_absolute() or path == Path(".") or ".." in path.parts:
        raise ValueError("compression paths must stay relative")
    return path


__all__ = [
    "AdaptiveCompressionProfile",
    "CompressionGroup",
    "CompressionPoint",
    "build_adaptive_groups",
    "select_embedding_representative",
]
