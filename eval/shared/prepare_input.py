"""Prepare a fresh evaluation source from an exact hash-bound allowlist.

This is evaluator tooling, not a MediaSense runtime dependency or blind judge.
Keep its operator manifest and this repository outside the judging context.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
from pathlib import Path
import shutil
import tempfile


def operator_manifest_path(
    source_root: Path, destination: Path, manifest: Path
) -> Path:
    """Resolve actual destinations before any copy or manifest write."""
    try:
        root = source_root.resolve()
        target = destination.resolve()
        resolved = manifest.resolve()
    except (OSError, RuntimeError) as error:
        raise ValueError("Cannot resolve evaluation output boundaries") from error
    if resolved.is_relative_to(target) or resolved.is_relative_to(root):
        raise ValueError(
            "Operator manifest must stay outside the source and judged source"
        )
    if manifest.is_symlink() or resolved.exists():
        raise ValueError("Operator manifest must be a new regular file")
    return resolved


def write_operator_manifest(
    source_root: Path, destination: Path, manifest_path: Path, manifest: dict
) -> None:
    resolved = operator_manifest_path(source_root, destination, manifest_path)
    # Open each canonical parent without following links, then create the leaf
    # exclusively relative to the pinned directory. Never overwrite a prior
    # file or follow a link introduced between validation and creation.
    parent_fd = os.open(resolved.anchor, os.O_RDONLY | os.O_DIRECTORY)
    try:
        for component in resolved.parent.parts[1:]:
            child_fd = os.open(
                component,
                os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW,
                dir_fd=parent_fd,
            )
            os.close(parent_fd)
            parent_fd = child_fd
        fd = os.open(
            resolved.name,
            os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW,
            0o600,
            dir_fd=parent_fd,
        )
        with os.fdopen(fd, "w", encoding="utf-8") as stream:
            stream.write(json.dumps(manifest, ensure_ascii=False, indent=2))
    finally:
        os.close(parent_fd)


def prepare(
    source_root: Path, allowed: dict[str, str], destination: Path, *, path_policy: str
) -> dict:
    if path_policy not in {"preserve", "opaque"}:
        raise ValueError("Declare whether original human path semantics are allowed")
    root = source_root.absolute()
    target = destination.resolve()
    if root.is_symlink() or not root.is_dir():
        raise ValueError("Source root must be a regular directory")
    root = root.resolve()
    if target.exists() or target.is_symlink() or target.resolve().is_relative_to(root):
        raise ValueError("Destination must be new and outside the source")
    if not allowed:
        raise ValueError("An explicit nonempty input allowlist is required")
    checked = []
    for index, (relative, digest) in enumerate(sorted(allowed.items())):
        path = Path(relative)
        if path.is_absolute() or not path.parts or ".." in path.parts:
            raise ValueError(f"Invalid allowlist path at row {index}")
        source = root / path
        if (
            any(part.is_symlink() for part in (source, *source.parents))
            or not source.is_file()
        ):
            raise ValueError(f"Non-regular allowlist input at row {index}")
        with source.open("rb") as stream:
            if (
                not isinstance(digest, str)
                or hashlib.file_digest(stream, "sha256").hexdigest() != digest
            ):
                raise ValueError(f"Input hash mismatch at row {index}")
        output = (
            path
            if path_policy == "preserve"
            else Path(f"item-{index:06d}{path.suffix.lower()}")
        )
        checked.append((path, source, output, digest))
    target.parent.mkdir(parents=True, exist_ok=True)
    temporary = Path(tempfile.mkdtemp(prefix=".eval-input-", dir=target.parent))
    try:
        for _relative, source, output, digest in checked:
            copied = temporary / output
            copied.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(source, copied)
            with copied.open("rb") as stream:
                if hashlib.file_digest(stream, "sha256").hexdigest() != digest:
                    raise ValueError("Input changed during staging")
        temporary.rename(target)
    except BaseException:
        shutil.rmtree(temporary)
        raise
    return {
        "path_policy": path_policy,
        "allowed": [
            {"original": str(path), "staged": str(output), "sha256": digest}
            for path, _source, output, digest in checked
        ],
        "limitations": "Copies isolate files, not Agent memory, inherited context, filesystem tools, or external retrieval. A blind judge needs a separately restricted clean context.",
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source-root", type=Path, required=True)
    parser.add_argument(
        "--allowlist",
        type=Path,
        required=True,
        help="JSON object of relative paths to SHA-256",
    )
    parser.add_argument("--destination", type=Path, required=True)
    parser.add_argument("--path-policy", choices=("preserve", "opaque"), required=True)
    parser.add_argument("--operator-manifest", type=Path, required=True)
    args = parser.parse_args()
    try:
        operator_path = operator_manifest_path(
            args.source_root, args.destination, args.operator_manifest
        )
        if not operator_path.parent.is_dir():
            raise ValueError("Operator manifest parent must already exist")
    except ValueError as error:
        parser.error(str(error))
    manifest = prepare(
        args.source_root,
        json.loads(args.allowlist.read_text()),
        args.destination,
        path_policy=args.path_policy,
    )
    write_operator_manifest(
        args.source_root, args.destination, args.operator_manifest, manifest
    )
    print(
        json.dumps(
            {
                "source_root": str(args.destination),
                "file_count": len(manifest["allowed"]),
                "path_policy": args.path_policy,
            }
        )
    )


if __name__ == "__main__":
    main()
