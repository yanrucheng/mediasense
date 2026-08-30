"""Recoverable, non-overwriting publication of immutable Frozen Plans."""

from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any
from uuid import uuid4

from jsonschema import Draft202012Validator

from mediasense.frozen_plan import FrozenPlanValidationError, validate_frozen_plan


class PublicationConflict(RuntimeError):
    """An existing artifact disagrees with the reserved seal outcome."""


class FrozenPlanPublisher:
    def __init__(
        self,
        frozen_dir: Path,
        validator: Draft202012Validator,
    ) -> None:
        self.frozen_dir = Path(frozen_dir)
        self.validator = validator

    def artifact_path(self, plan_ref: str) -> Path:
        import hashlib

        key = hashlib.sha256(plan_ref.encode("utf-8")).hexdigest()
        return self.frozen_dir / f"{key}.json"

    def serialize(self, frozen_plan: dict[str, Any]) -> bytes:
        self.verify(frozen_plan)
        return (
            json.dumps(
                frozen_plan,
                ensure_ascii=False,
                sort_keys=True,
                separators=(",", ":"),
            )
            + "\n"
        ).encode("utf-8")

    def publish(self, path: Path, expected_bytes: bytes) -> None:
        path = Path(path)
        try:
            self.frozen_dir.mkdir(parents=True, exist_ok=True)
            if path.parent.resolve() != self.frozen_dir.resolve():
                raise PublicationConflict(
                    "Frozen Plan path escapes the frozen directory"
                )
            if path.exists():
                self._verify_existing(path, expected_bytes)
                return

            temporary = path.with_name(f".{path.name}.{uuid4().hex}.tmp")
            try:
                with temporary.open("xb") as stream:
                    stream.write(expected_bytes)
                    stream.flush()
                    os.fsync(stream.fileno())
                try:
                    os.link(temporary, path)
                except FileExistsError:
                    self._verify_existing(path, expected_bytes)
                else:
                    self._fsync_directory(path.parent)
                    self._verify_existing(path, expected_bytes)
            finally:
                try:
                    temporary.unlink()
                except FileNotFoundError:
                    pass
        except PublicationConflict:
            raise
        except OSError as exc:
            raise PublicationConflict("Frozen Plan publication failed") from exc

    def read_verified(self, path: Path) -> dict[str, Any]:
        try:
            data = Path(path).read_bytes()
            value = json.loads(data.decode("utf-8"))
        except (OSError, UnicodeDecodeError, json.JSONDecodeError) as exc:
            raise PublicationConflict(
                "Frozen Plan artifact is missing or invalid"
            ) from exc
        if not isinstance(value, dict):
            raise PublicationConflict("Frozen Plan artifact is not an object")
        self.verify(value)
        return value

    def verify(self, frozen_plan: dict[str, Any]) -> None:
        try:
            validate_frozen_plan(frozen_plan, validator=self.validator)
        except FrozenPlanValidationError as error:
            raise PublicationConflict(str(error)) from error

    @staticmethod
    def _verify_existing(path: Path, expected_bytes: bytes) -> None:
        try:
            observed = path.read_bytes()
        except OSError as exc:
            raise PublicationConflict("Frozen Plan artifact cannot be read") from exc
        if observed != expected_bytes:
            raise PublicationConflict(
                "Frozen Plan artifact conflicts with reserved bytes"
            )

    @staticmethod
    def _fsync_directory(directory: Path) -> None:
        descriptor = os.open(directory, os.O_RDONLY)
        try:
            os.fsync(descriptor)
        finally:
            os.close(descriptor)
