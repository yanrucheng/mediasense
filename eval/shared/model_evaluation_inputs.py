"""Hash-bound local evaluation inputs; never read historical model results."""

from __future__ import annotations

from datetime import datetime
import hashlib
import json
import math
from pathlib import Path
import subprocess
from zoneinfo import ZoneInfo

from PIL import Image

from prepare_input import prepare


def digest(path: Path) -> str:
    with path.open("rb") as stream:
        return hashlib.file_digest(stream, "sha256").hexdigest()


def fingerprint(value: object) -> str:
    return hashlib.sha256(
        json.dumps(
            value, sort_keys=True, ensure_ascii=False, separators=(",", ":")
        ).encode()
    ).hexdigest()


def write_json(path: Path, value: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("x", encoding="utf-8") as stream:
        json.dump(value, stream, ensure_ascii=False, indent=2, allow_nan=False)
        stream.write("\n")


def checked_file(root: Path, relative: str, expected: str) -> Path:
    part = Path(relative)
    if part.is_absolute() or ".." in part.parts or not part.parts:
        raise ValueError(f"Invalid relative input: {relative}")
    path = root / part
    if any(p.is_symlink() for p in (path, *path.parents)) or not path.is_file():
        raise ValueError(f"Input must be a regular file: {relative}")
    if digest(path) != expected:
        raise ValueError(f"SHA-256 mismatch: {relative}")
    return path


def outside(path: Path, *roots: Path) -> Path:
    resolved = path.resolve()
    if any(resolved.is_relative_to(root.resolve()) for root in roots):
        raise ValueError("Evaluation output must be outside the fixture")
    return resolved


def stage_fixture(config: dict, destination: Path) -> dict:
    """Reuse the existing allowlist copier to exclude unlisted package additions."""
    fixture = config["fixture"]
    source = Path(fixture["original_package_root"]).resolve()
    manifest = checked_file(
        source, "manifests/SHA256SUMS", fixture["checksum_manifest_sha256"]
    )
    allowed = {}
    for line in manifest.read_text().splitlines():
        sha, relative = line.split("  ", 1)
        relative = relative.removeprefix("./")
        if relative in allowed:
            raise ValueError("Duplicate checksum entry")
        allowed[relative] = sha
    allowed["manifests/SHA256SUMS"] = fixture["checksum_manifest_sha256"]
    copied = prepare(source, allowed, destination, path_policy="preserve")
    return {"files": len(copied["allowed"]), "destination": str(destination.resolve())}


def source_rows(config: dict) -> tuple[Path, list[dict]]:
    fixture = config["fixture"]
    package = Path(fixture["package_root"]).resolve()
    checked_file(package, "manifests/SHA256SUMS", fixture["checksum_manifest_sha256"])
    manifest = checked_file(
        package, "manifests/media-manifest.jsonl", fixture["media_manifest_sha256"]
    )
    # Deliberately discard cached_metadata, representatives, bundles, and names.
    rows = [
        {
            "path": row["path"],
            "kind": row["media_type"],
            "sha256": row["derived_sha256"],
        }
        for row in map(json.loads, manifest.read_text().splitlines())
    ]
    rows.sort(key=lambda row: row["path"])
    if len(rows) != fixture["expected_media_count"] or len(
        {r["path"] for r in rows}
    ) != len(rows):
        raise ValueError("Unexpected or duplicate source inventory")
    if any(r["kind"] not in {"image", "video"} for r in rows):
        raise ValueError("Only manifest images and videos are evaluation inputs")
    root = package / fixture["media_subdirectory"]
    for row in rows:
        checked_file(root, row["path"], row["sha256"])
    return root, rows


def tool_version(executable: str) -> str:
    return subprocess.check_output([executable, "-version"], text=True).splitlines()[0]


def capture_time(
    path: Path, *, image: Image.Image | None = None, probe: dict | None = None
) -> tuple[float, str]:
    if image is not None:
        exif = image.getexif()
        details = exif.get_ifd(34665) if 34665 in exif else exif
        for key in (36867, 36868):
            value = details.get(key)
            if isinstance(value, str):
                try:
                    parsed = datetime.strptime(value, "%Y:%m:%d %H:%M:%S")
                    offset = details.get(36881 if key == 36867 else 36882)
                    if isinstance(offset, str):
                        parsed = datetime.fromisoformat(parsed.isoformat() + offset)
                    else:
                        parsed = parsed.replace(tzinfo=ZoneInfo("Asia/Shanghai"))
                    return parsed.timestamp(), f"exif:{key};naive=Asia/Shanghai"
                except ValueError:
                    pass
    if probe is not None:
        for section in [probe.get("format", {}), *probe.get("streams", [])]:
            value = section.get("tags", {}).get("creation_time")
            if value:
                try:
                    parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
                    if parsed.tzinfo is None:
                        parsed = parsed.replace(tzinfo=ZoneInfo("UTC"))
                    return parsed.timestamp(), "ffprobe:creation_time;naive=UTC"
                except ValueError:
                    pass
    return path.stat().st_mtime, "filesystem:mtime;fallback"


def nearest_frames(probe: dict, fractions: list[float]) -> list[tuple[int, float]]:
    duration = float(probe["format"]["duration"])
    times = [float(frame["best_effort_timestamp_time"]) for frame in probe["frames"]]
    if (
        not times
        or not math.isfinite(duration)
        or duration <= 0
        or not all(map(math.isfinite, times))
    ):
        raise ValueError("Video has no usable duration/frame timestamps")
    # Frame indices, not approximate seeks, bind extraction. Ties use the earlier frame.
    return [
        min(
            enumerate(times),
            key=lambda entry: (abs(entry[1] - duration * fraction), entry[0]),
        )
        for fraction in fractions
    ]


def prepare_inputs(config: dict, destination: Path) -> dict:
    if config["inputs"].get("mode") == "mediasense_business":
        from model_evaluation_business_inputs import prepare_business_inputs

        return prepare_business_inputs(config, destination)
    root, sources = source_rows(config)
    destination = outside(destination, *fixture_roots(config))
    destination.mkdir(parents=True, exist_ok=False)
    policy = config["inputs"]
    fractions = policy["video_fractions"]
    if not fractions or any(not 0 <= value < 1 for value in fractions):
        raise ValueError("Frame fractions must be in [0, 1)")
    versions = {name: tool_version(policy[name]) for name in ("ffmpeg", "ffprobe")}
    if versions != policy["tool_versions"]:
        raise ValueError(
            "Video decoder version changed; explicitly rebaseline the input recipe"
        )
    inputs = []
    for source_index, source in enumerate(sources):
        path = root / source["path"]
        slots = [None] if source["kind"] == "image" else fractions
        records = [
            {
                "id": f"{source_index:05d}:{slot:02d}",
                "source": source["path"],
                "source_sha256": source["sha256"],
                "kind": source["kind"],
                "fraction": fraction,
                "state": "failed",
            }
            for slot, fraction in enumerate(slots)
        ]
        try:
            if source["kind"] == "image":
                with Image.open(path) as opened:
                    opened.load()
                    timestamp, basis = capture_time(path, image=opened)
                records[0].update(
                    image_path=str(path),
                    image_sha256=source["sha256"],
                    timestamp=timestamp,
                    time_basis=basis,
                    state="ready",
                )
            else:
                result = subprocess.run(
                    [
                        policy["ffprobe"],
                        "-v",
                        "error",
                        "-threads",
                        "1",
                        "-select_streams",
                        "v:0",
                        "-show_entries",
                        "frame=best_effort_timestamp_time:format=duration:format_tags=creation_time:stream_tags=creation_time",
                        "-of",
                        "json",
                        str(path),
                    ],
                    capture_output=True,
                    text=True,
                    timeout=120,
                    check=True,
                )
                probe = json.loads(result.stdout)
                selected = nearest_frames(probe, fractions)
                indices = sorted({index for index, _ in selected})
                frame_dir = destination / "frames" / f"{source_index:05d}"
                frame_dir.mkdir(parents=True)
                expression = "+".join(f"eq(n,{index})" for index in indices)
                subprocess.run(
                    [
                        policy["ffmpeg"],
                        "-v",
                        "error",
                        "-nostdin",
                        "-noautorotate",
                        "-threads",
                        "1",
                        "-i",
                        str(path),
                        "-vf",
                        f"select='{expression}'",
                        "-fps_mode",
                        "vfr",
                        "-frames:v",
                        str(len(indices)),
                        "-filter_threads",
                        "1",
                        "-threads",
                        "1",
                        "-pix_fmt",
                        "rgb24",
                        str(frame_dir / "%03d.png"),
                    ],
                    capture_output=True,
                    text=True,
                    timeout=120,
                    check=True,
                )
                frames = {
                    index: frame_dir / f"{number:03d}.png"
                    for number, index in enumerate(indices, 1)
                }
                timestamp, basis = capture_time(path, probe=probe)
                for record, (index, pts) in zip(records, selected, strict=True):
                    with Image.open(frames[index]) as opened:
                        opened.load()
                    record.update(
                        image_path=str(frames[index]),
                        image_sha256=digest(frames[index]),
                        frame_index=index,
                        pts_seconds=pts,
                        timestamp=timestamp + pts,
                        time_basis=basis + "+frame_pts",
                        state="ready",
                    )
        except (OSError, ValueError, KeyError, subprocess.SubprocessError) as error:
            detail = (
                error.stderr
                if isinstance(error, subprocess.CalledProcessError)
                else str(error)
            )
            for record in records:
                record.update(
                    state="failed",
                    error=f"{type(error).__name__}: {str(detail)[-1200:]}",
                )
        inputs.extend(records)
        if (source_index + 1) % 100 == 0:
            print(f"prepared {source_index + 1}/{len(sources)} sources", flush=True)
    # Detect a source changed during decode; never publish a misleading snapshot.
    source_rows(config)
    value = {
        "source_root": str(root),
        "source_count": len(sources),
        "source_fingerprint": fingerprint(sources),
        "recipe": policy,
        "inputs": inputs,
    }
    value["input_fingerprint"] = input_fingerprint(value)
    write_json(destination / "inputs.json", value)
    return {
        key: value[key]
        for key in ("source_count", "source_fingerprint", "input_fingerprint")
    }


def input_fingerprint(prepared: dict) -> str:
    return fingerprint(
        {
            "recipe": prepared["recipe"],
            "source_fingerprint": prepared["source_fingerprint"],
            "inputs": [
                {
                    key: value
                    for key, value in row.items()
                    if key not in {"image_path", "error"}
                }
                for row in prepared["inputs"]
            ],
        }
    )


def validate_inputs(config: dict, path: Path) -> dict:
    if config["inputs"].get("mode") == "mediasense_business":
        from model_evaluation_business_inputs import validate_business_inputs

        return validate_business_inputs(config, path)
    prepared = json.loads(path.read_text())
    root, sources = source_rows(config)
    if (
        str(root) != prepared["source_root"]
        or fingerprint(sources) != prepared["source_fingerprint"]
        or prepared["source_count"] != len(sources)
    ):
        raise ValueError("Prepared sources do not match this fixture")
    expected_ids = [
        f"{index:05d}:{slot:02d}"
        for index, row in enumerate(sources)
        for slot in range(
            1 if row["kind"] == "image" else len(config["inputs"]["video_fractions"])
        )
    ]
    if [row["id"] for row in prepared["inputs"]] != expected_ids:
        raise ValueError("Prepared inputs are missing, reordered, or duplicated")
    if (
        prepared["recipe"] != config["inputs"]
        or input_fingerprint(prepared) != prepared["input_fingerprint"]
    ):
        raise ValueError("Prepared input recipe or records changed")
    if prepared["input_fingerprint"] != config["expected_input_fingerprint"]:
        raise ValueError(
            "Input fingerprint differs from the frozen baseline; rebaseline explicitly"
        )
    for row in prepared["inputs"]:
        if row["state"] not in {"ready", "failed"}:
            raise ValueError(f"Unknown prepared input state: {row['id']}")
        if (
            row["state"] == "ready"
            and digest(Path(row["image_path"])) != row["image_sha256"]
        ):
            raise ValueError(f"Prepared raster changed: {row['id']}")
    return prepared


def fixture_roots(config: dict) -> list[Path]:
    return [
        Path(config["fixture"][key])
        for key in ("package_root", "original_package_root")
        if key in config["fixture"]
    ]
