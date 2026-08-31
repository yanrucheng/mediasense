"""Resolve and create portable or machine-local MediaSense Dataset workspaces."""

from __future__ import annotations

import hashlib
import json
import os
import shutil
import sqlite3
import stat
import sys
from collections.abc import Callable, Mapping
from dataclasses import asdict, dataclass
from datetime import UTC, datetime
from enum import StrEnum
from pathlib import Path
from typing import Any
from uuid import uuid4

from mediasense.dataset_reference import dataset_id_from_ref, dataset_ref_from_id
from mediasense.precheck.source_attachment import (
    AttachmentState,
    SourceAttachmentError,
    probe_source_attachment,
)
from mediasense.volume import (
    PathIdentity,
    find_mount_root,
    is_non_system_volume,
    observe_path_identity,
)

from .config import ConfigurationError, RuntimeConfig, load_runtime_config
from .versioning import DATASET_MANIFEST_VERSION, DATASET_STORE_VERSIONS

_MANIFEST_NAME = "dataset.json"
_FORMAT = "mediasense.dataset"
_STORES = ("precheck", "plan", "geo", "apply")


class DatasetOpenError(RuntimeError):
    """A Dataset could not be opened without ambiguity or unsafe fallback."""

    def __init__(self, code: str, message: str, *, path: Path | None = None) -> None:
        super().__init__(message)
        self.code = code
        self.path = path


class WorkspaceTier(StrEnum):
    EXPLICIT = "explicit"
    EXTERNAL_VOLUME = "external_volume"
    LOCAL = "local"


@dataclass(frozen=True, slots=True)
class SourceLocator:
    kind: str
    value: str
    volume_identity: str
    root_identity: str
    identity_strength: str


@dataclass(frozen=True, slots=True)
class DatasetManifest:
    format: str
    format_version: int
    dataset_ref: str
    created_at: str
    placement: str
    source: SourceLocator
    stores: Mapping[str, int]

    @classmethod
    def from_value(cls, value: object, *, path: Path) -> DatasetManifest:
        if not isinstance(value, Mapping):
            raise DatasetOpenError(
                "manifest_invalid", "Dataset manifest must be an object.", path=path
            )
        expected = {
            "format",
            "format_version",
            "dataset_ref",
            "created_at",
            "placement",
            "source",
            "stores",
        }
        if set(value) != expected:
            raise DatasetOpenError(
                "manifest_invalid",
                "Dataset manifest has missing or unknown fields.",
                path=path,
            )
        if value["format"] != _FORMAT:
            raise DatasetOpenError(
                "manifest_invalid",
                "Dataset manifest format is not recognized.",
                path=path,
            )
        manifest_version = value["format_version"]
        if not isinstance(manifest_version, int):
            raise DatasetOpenError(
                "manifest_invalid", "Dataset manifest version is invalid.", path=path
            )
        if manifest_version > DATASET_MANIFEST_VERSION:
            raise DatasetOpenError(
                "manifest_newer",
                f"Dataset manifest version {manifest_version} is newer than supported version {DATASET_MANIFEST_VERSION}.",
                path=path,
            )
        if manifest_version != DATASET_MANIFEST_VERSION:
            raise DatasetOpenError(
                "manifest_unsupported",
                f"Dataset manifest version {manifest_version} has no supported migration.",
                path=path,
            )
        dataset_ref = value["dataset_ref"]
        try:
            dataset_id_from_ref(dataset_ref)
        except ValueError:
            raise DatasetOpenError(
                "manifest_invalid", "Dataset reference is invalid.", path=path
            ) from None
        source_value = value["source"]
        if not isinstance(source_value, Mapping):
            raise DatasetOpenError(
                "manifest_invalid", "Dataset source descriptor is invalid.", path=path
            )
        source_keys = {
            "kind",
            "value",
            "volume_identity",
            "root_identity",
            "identity_strength",
        }
        if set(source_value) != source_keys or any(
            not isinstance(source_value[item], str) or not source_value[item]
            for item in source_keys
        ):
            raise DatasetOpenError(
                "manifest_invalid",
                "Dataset source descriptor is incomplete.",
                path=path,
            )
        stores = value["stores"]
        if not isinstance(stores, Mapping) or set(stores) != set(_STORES):
            raise DatasetOpenError(
                "manifest_invalid", "Dataset store versions are incomplete.", path=path
            )
        normalized_stores: dict[str, int] = {}
        for name in _STORES:
            store_version = stores[name]
            if not isinstance(store_version, int) or store_version < 1:
                raise DatasetOpenError(
                    "manifest_invalid",
                    f"Dataset store version for {name} is invalid.",
                    path=path,
                )
            supported = DATASET_STORE_VERSIONS[name]
            if store_version > supported:
                raise DatasetOpenError(
                    "store_newer",
                    f"Dataset {name} store version {store_version} is newer than supported version {supported}.",
                    path=path,
                )
            if store_version != supported:
                raise DatasetOpenError(
                    "store_unsupported",
                    f"Dataset {name} store version {store_version} has no supported migration.",
                    path=path,
                )
            normalized_stores[name] = store_version
        if value["placement"] not in {item.value for item in WorkspaceTier}:
            raise DatasetOpenError(
                "manifest_invalid", "Dataset placement tier is invalid.", path=path
            )
        if not isinstance(value["created_at"], str) or not value["created_at"]:
            raise DatasetOpenError(
                "manifest_invalid", "Dataset creation time is invalid.", path=path
            )
        return cls(
            format=_FORMAT,
            format_version=manifest_version,
            dataset_ref=dataset_ref,
            created_at=str(value["created_at"]),
            placement=str(value["placement"]),
            source=SourceLocator(**dict(source_value)),
            stores=normalized_stores,
        )

    def to_value(self) -> dict[str, object]:
        return {
            "format": self.format,
            "format_version": self.format_version,
            "dataset_ref": self.dataset_ref,
            "created_at": self.created_at,
            "placement": self.placement,
            "source": asdict(self.source),
            "stores": dict(self.stores),
        }

    @property
    def dataset_id(self) -> str:
        """Return the internal identifier carried by the public manifest ref."""

        return dataset_id_from_ref(self.dataset_ref)


@dataclass(frozen=True, slots=True)
class DatasetOpenResult:
    manifest: DatasetManifest
    source_root: Path
    workspace: Path
    tier: WorkspaceTier
    created: bool
    warnings: tuple[str, ...] = ()

    def to_value(self) -> dict[str, object]:
        return {
            "outcome": "ok",
            "dataset_ref": self.manifest.dataset_ref,
            "source_root": str(self.source_root),
            "workspace": str(self.workspace),
            "selection_tier": self.tier.value,
            "created": self.created,
            "manifest_version": self.manifest.format_version,
            "store_versions": dict(self.manifest.stores),
            "warnings": list(self.warnings),
        }


IdentityObserver = Callable[[Path], PathIdentity]
MountResolver = Callable[[Path], Path]


class DatasetResolver:
    """Resolve one source through explicit, portable, then local state."""

    def __init__(
        self,
        *,
        local_root: Path | None = None,
        mount_resolver: MountResolver = find_mount_root,
        identity_observer: IdentityObserver = observe_path_identity,
        id_factory: Callable[[], str] | None = None,
        clock: Callable[[], datetime] | None = None,
    ) -> None:
        self.local_root = Path(local_root or default_local_dataset_root())
        self._mount_resolver = mount_resolver
        self._identity_observer = identity_observer
        self._id_factory = id_factory or (lambda: uuid4().hex)
        self._clock = clock or (lambda: datetime.now(UTC))

    def open(
        self,
        source_root: Path,
        *,
        explicit_workspace: Path | None = None,
    ) -> DatasetOpenResult:
        source = Path(source_root).expanduser().absolute()
        if source.is_symlink():
            raise DatasetOpenError(
                "source_root_symlink",
                "The Dataset source root must not be a symbolic link.",
                path=source,
            )
        if not source.exists():
            raise DatasetOpenError(
                "source_unavailable",
                "The Dataset source root does not exist.",
                path=source,
            )
        if not source.is_dir():
            raise DatasetOpenError(
                "source_not_directory",
                "The Dataset source root is not a directory.",
                path=source,
            )

        identity = self._identity_observer(source)
        external = is_non_system_volume(source, mount_root=identity.mount_root)
        locator = _source_locator(source, identity, external=external)

        if explicit_workspace is not None:
            workspace = Path(explicit_workspace).expanduser().absolute()
            return self._open_exact(
                source, workspace, WorkspaceTier.EXPLICIT, locator, create=True
            )

        external_workspace: Path | None = None
        if external:
            external_root = identity.mount_root / ".mediasense" / "datasets"
            if external_root.exists() and (
                not external_root.is_dir() or not os.access(external_root, os.R_OK)
            ):
                raise DatasetOpenError(
                    "workspace_unavailable",
                    "The external Dataset root exists but cannot be inspected safely.",
                    path=external_root,
                )
            external_workspace = _automatic_workspace(
                external_root, locator, portable=True
            )
            if external_workspace.exists():
                return self._open_exact(
                    source,
                    external_workspace,
                    WorkspaceTier.EXTERNAL_VOLUME,
                    locator,
                    create=False,
                )

        local_workspace = _automatic_workspace(self.local_root, locator, portable=False)
        if local_workspace.exists():
            return self._open_exact(
                source,
                local_workspace,
                WorkspaceTier.LOCAL,
                locator,
                create=False,
            )

        warnings: list[str] = []
        if external_workspace is not None:
            try:
                return self._open_exact(
                    source,
                    external_workspace,
                    WorkspaceTier.EXTERNAL_VOLUME,
                    locator,
                    create=True,
                )
            except DatasetOpenError as error:
                if error.code not in {
                    "workspace_unavailable",
                    "workspace_unsafe",
                    "workspace_nested_in_source",
                }:
                    raise
                warnings.append(f"portable_workspace_unavailable:{error.code}")

        opened = self._open_exact(
            source,
            local_workspace,
            WorkspaceTier.LOCAL,
            locator,
            create=True,
        )
        return DatasetOpenResult(
            manifest=opened.manifest,
            source_root=opened.source_root,
            workspace=opened.workspace,
            tier=opened.tier,
            created=opened.created,
            warnings=tuple(warnings) + opened.warnings,
        )

    def _open_exact(
        self,
        source: Path,
        workspace: Path,
        tier: WorkspaceTier,
        locator: SourceLocator,
        *,
        create: bool,
    ) -> DatasetOpenResult:
        if workspace.is_symlink():
            raise DatasetOpenError(
                "workspace_symlink",
                "The Dataset workspace must not be a symbolic link.",
                path=workspace,
            )
        if _is_within(workspace, source):
            raise DatasetOpenError(
                "workspace_nested_in_source",
                "The Dataset workspace must not be inside the source root.",
                path=workspace,
            )
        manifest_path = workspace / _MANIFEST_NAME
        if workspace.exists():
            if not workspace.is_dir():
                raise DatasetOpenError(
                    "workspace_invalid",
                    "The Dataset workspace is not a directory.",
                    path=workspace,
                )
            if not manifest_path.exists():
                if any(workspace.iterdir()):
                    raise DatasetOpenError(
                        "manifest_missing",
                        "The selected Dataset workspace is non-empty but has no manifest.",
                        path=workspace,
                    )
            else:
                manifest = _read_manifest(manifest_path)
                _verify_manifest_source(manifest, locator, path=manifest_path)
                _verify_component_stores(workspace, manifest)
                return DatasetOpenResult(
                    manifest,
                    source,
                    workspace,
                    tier,
                    False,
                    _permission_warnings(workspace, manifest_path),
                )
        if not create:
            raise DatasetOpenError(
                "dataset_not_found",
                "No matching Dataset workspace exists.",
                path=workspace,
            )
        return self._create(source, workspace, tier, locator)

    def _create(
        self,
        source: Path,
        workspace: Path,
        tier: WorkspaceTier,
        locator: SourceLocator,
    ) -> DatasetOpenResult:
        try:
            workspace.parent.mkdir(parents=True, exist_ok=True)
        except OSError as error:
            raise DatasetOpenError(
                "workspace_unavailable",
                f"The Dataset workspace parent cannot be created: {error}",
                path=workspace.parent,
            ) from error
        if workspace.exists():
            try:
                workspace.rmdir()
            except OSError as error:
                raise DatasetOpenError(
                    "workspace_unavailable",
                    "The empty Dataset workspace cannot be initialized safely.",
                    path=workspace,
                ) from error
        staging = workspace.with_name(f".{workspace.name}.creating-{uuid4().hex}")
        try:
            staging.mkdir()
            probe = probe_source_attachment(source, staging / "precheck")
            if probe.state is not AttachmentState.AVAILABLE:
                raise DatasetOpenError(
                    "source_unavailable",
                    probe.blocked_reason or "The source root is unavailable.",
                    path=source,
                )
            if not probe.capabilities.workspace_atomic_replace:
                raise DatasetOpenError(
                    "workspace_unsafe",
                    "The Dataset workspace does not provide verified atomic replacement.",
                    path=workspace,
                )
            for store in _STORES:
                (staging / store).mkdir(exist_ok=True)
            try:
                dataset_ref = dataset_ref_from_id(self._id_factory())
            except ValueError as error:
                raise DatasetOpenError(
                    "workspace_unsafe",
                    f"The generated Dataset identifier is invalid: {error}",
                    path=workspace,
                ) from error
            manifest = DatasetManifest(
                format=_FORMAT,
                format_version=DATASET_MANIFEST_VERSION,
                dataset_ref=dataset_ref,
                created_at=self._clock().astimezone(UTC).isoformat(),
                placement=tier.value,
                source=locator,
                stores=dict(DATASET_STORE_VERSIONS),
            )
            _write_manifest(staging / _MANIFEST_NAME, manifest)
            os.replace(staging, workspace)
        except DatasetOpenError:
            shutil.rmtree(staging, ignore_errors=True)
            raise
        except (OSError, SourceAttachmentError) as error:
            shutil.rmtree(staging, ignore_errors=True)
            raise DatasetOpenError(
                "workspace_unsafe", str(error) or type(error).__name__, path=workspace
            ) from error
        return DatasetOpenResult(
            manifest,
            source,
            workspace,
            tier,
            True,
            _restrict_workspace_permissions(workspace),
        )


class DatasetOpenTool:
    """Public onboarding boundary shared by CLI and MCP adapters."""

    name = "mediasense.dataset.open"

    def __init__(self, resolver: DatasetResolver) -> None:
        self.resolver = resolver

    def open(
        self, source_root: str, workspace: str | None = None
    ) -> tuple[DatasetOpenResult, RuntimeConfig, dict[str, object]]:
        if not source_root.strip():
            raise DatasetOpenError(
                "invalid_request", "source_root must be a non-empty path."
            )
        if workspace is not None and not workspace.strip():
            raise DatasetOpenError(
                "invalid_request", "workspace must be a non-empty path."
            )
        load_runtime_config()
        opened = self.resolver.open(
            Path(source_root),
            explicit_workspace=None if workspace is None else Path(workspace),
        )
        config = load_runtime_config(dataset_workspace=opened.workspace)
        result = opened.to_value()
        result["configuration"] = config.public_value()
        return opened, config, result

    def handle(self, request: Mapping[str, object]) -> dict[str, object]:
        if not isinstance(request, Mapping):
            return _error("invalid_request", "Dataset open request must be an object.")
        unknown = set(request) - {"source_root", "workspace"}
        if unknown:
            return _error(
                "invalid_request", f"Unknown Dataset open fields: {sorted(unknown)}"
            )
        source = request.get("source_root")
        workspace = request.get("workspace")
        if not isinstance(source, str):
            return _error("invalid_request", "source_root must be a non-empty path.")
        if workspace is not None and not isinstance(workspace, str):
            return _error("invalid_request", "workspace must be a non-empty path.")
        try:
            _opened, _config, result = self.open(source, workspace)
            return result
        except (DatasetOpenError, ConfigurationError) as error:
            code = (
                error.code
                if isinstance(error, DatasetOpenError)
                else "configuration_invalid"
            )
            result = _error(code, str(error))
            if isinstance(error, DatasetOpenError) and error.path is not None:
                result["path"] = str(error.path)
            return result


def default_local_dataset_root(
    *,
    platform_name: str | None = None,
    home: Path | None = None,
) -> Path:
    override = os.environ.get("MEDIASENSE_DATA_HOME")
    if override:
        return Path(override).expanduser().absolute() / "datasets"
    platform_value = platform_name or sys.platform
    home_value = Path(home or Path.home())
    if platform_value == "darwin":
        return (
            home_value / "Library" / "Application Support" / "MediaSense" / "datasets"
        )
    if platform_value == "win32":
        local = os.environ.get("LOCALAPPDATA")
        return (
            Path(local) / "MediaSense" / "datasets"
            if local
            else home_value / "MediaSense" / "datasets"
        )
    data_home = os.environ.get("XDG_DATA_HOME")
    base = (
        Path(data_home).expanduser() if data_home else home_value / ".local" / "share"
    )
    return base / "mediasense" / "datasets"


def inspect_workspace(workspace: Path) -> dict[str, object]:
    """Read one Dataset manifest and store versions without mutating the workspace."""

    root = Path(workspace).expanduser().absolute()
    manifest = _read_manifest(root / _MANIFEST_NAME)
    _verify_component_stores(root, manifest)
    return {
        "outcome": "ok",
        "dataset_ref": manifest.dataset_ref,
        "workspace": str(root),
        "placement": manifest.placement,
        "source": asdict(manifest.source),
        "manifest_version": manifest.format_version,
        "store_versions": dict(manifest.stores),
    }


def _source_locator(
    source: Path, identity: PathIdentity, *, external: bool
) -> SourceLocator:
    if external:
        relative = source.relative_to(identity.mount_root)
        kind = "volume_relative"
        value = "." if relative == Path(".") else relative.as_posix()
    else:
        kind = "absolute"
        value = str(source)
    return SourceLocator(
        kind=kind,
        value=value,
        volume_identity=identity.volume_identity,
        root_identity=identity.root_identity,
        identity_strength=identity.identity_strength,
    )


def _automatic_workspace(root: Path, locator: SourceLocator, *, portable: bool) -> Path:
    identity_parts = [locator.kind, locator.value]
    if not portable and locator.kind == "volume_relative":
        identity_parts.append(locator.volume_identity)
    identity = "\0".join(identity_parts).encode()
    key = hashlib.sha256(identity).hexdigest()[:24]
    return root / f"dataset-{key}"


def _read_manifest(path: Path) -> DatasetManifest:
    try:
        value: Any = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as error:
        raise DatasetOpenError(
            "manifest_invalid", f"Dataset manifest cannot be read: {error}", path=path
        ) from error
    return DatasetManifest.from_value(value, path=path)


def _write_manifest(path: Path, manifest: DatasetManifest) -> None:
    temporary = path.with_suffix(".json.tmp")
    encoded = (
        json.dumps(manifest.to_value(), ensure_ascii=False, indent=2, sort_keys=True)
        + "\n"
    )
    try:
        with temporary.open("x", encoding="utf-8") as stream:
            stream.write(encoded)
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(temporary, path)
    finally:
        temporary.unlink(missing_ok=True)


def _verify_manifest_source(
    manifest: DatasetManifest, current: SourceLocator, *, path: Path
) -> None:
    if manifest.source.kind != current.kind or manifest.source.value != current.value:
        raise DatasetOpenError(
            "source_mismatch",
            "The Dataset workspace is bound to a different source locator.",
            path=path,
        )
    stable = (
        manifest.source.identity_strength == "stable_volume"
        and current.identity_strength == "stable_volume"
    )
    if stable and manifest.source.root_identity != current.root_identity:
        raise DatasetOpenError(
            "source_mismatch",
            "The Dataset workspace is bound to a different source identity.",
            path=path,
        )


def _verify_component_stores(workspace: Path, manifest: DatasetManifest) -> None:
    paths = {
        "precheck": workspace / "precheck" / "work.sqlite3",
        "plan": workspace / "plan" / "work.sqlite3",
        "geo": workspace / "geo" / "journal.sqlite3",
        "apply": workspace / "apply" / "work.sqlite3",
    }
    for name, database in paths.items():
        if not database.exists():
            continue
        try:
            with sqlite3.connect(f"file:{database}?mode=ro", uri=True) as connection:
                row = connection.execute(
                    "SELECT version FROM internal_schema WHERE singleton = 1"
                ).fetchone()
        except sqlite3.Error as error:
            raise DatasetOpenError(
                "store_unversioned",
                f"The Dataset {name} store has no readable schema version.",
                path=database,
            ) from error
        if row is None:
            raise DatasetOpenError(
                "store_unversioned",
                f"The Dataset {name} store has no schema version.",
                path=database,
            )
        actual = int(row[0])
        expected = int(manifest.stores[name])
        if actual > expected:
            raise DatasetOpenError(
                "store_newer",
                f"The Dataset {name} store version {actual} is newer than supported version {expected}.",
                path=database,
            )
        if actual != expected:
            raise DatasetOpenError(
                "store_unsupported",
                f"The Dataset {name} store version {actual} has no supported migration.",
                path=database,
            )


def _restrict_workspace_permissions(workspace: Path) -> tuple[str, ...]:
    warnings: list[str] = []
    for directory in (workspace, *(workspace / item for item in _STORES)):
        try:
            directory.chmod(0o700)
            if stat.S_IMODE(directory.stat().st_mode) & 0o077:
                warnings.append(f"workspace_permissions_broad:{directory}")
        except OSError:
            warnings.append(f"workspace_permissions_unverified:{directory}")
    manifest = workspace / _MANIFEST_NAME
    try:
        manifest.chmod(0o600)
        if stat.S_IMODE(manifest.stat().st_mode) & 0o077:
            warnings.append(f"manifest_permissions_broad:{manifest}")
    except OSError:
        warnings.append(f"workspace_permissions_unverified:{manifest}")
    return tuple(warnings)


def _permission_warnings(workspace: Path, manifest: Path) -> tuple[str, ...]:
    warnings: list[str] = []
    try:
        if stat.S_IMODE(workspace.stat().st_mode) & 0o077:
            warnings.append(f"workspace_permissions_broad:{workspace}")
        if stat.S_IMODE(manifest.stat().st_mode) & 0o077:
            warnings.append(f"manifest_permissions_broad:{manifest}")
    except OSError:
        warnings.append(f"workspace_permissions_unverified:{workspace}")
    return tuple(warnings)


def _is_within(candidate: Path, parent: Path) -> bool:
    try:
        candidate.resolve(strict=False).relative_to(parent.resolve(strict=False))
    except ValueError:
        return False
    return True


def _error(code: str, message: str) -> dict[str, object]:
    return {"outcome": "error", "error": {"code": code, "message": message}}
