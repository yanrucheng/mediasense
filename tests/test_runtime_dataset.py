from __future__ import annotations

import hashlib
import json
import sqlite3
import stat
import subprocess
from datetime import UTC, datetime
from pathlib import Path

import pytest
from jsonschema import Draft202012Validator

from mediasense.precheck.source_attachment import (
    UnsafeWorkspace,
    probe_source_attachment,
)
from mediasense.precheck import AccountingStore
from mediasense.runtime.dataset import (
    DatasetOpenError,
    DatasetOpenTool,
    DatasetResolver,
    WorkspaceTier,
    default_local_dataset_root,
    inspect_workspace,
)
from mediasense.runtime.resources import load_contract
from mediasense.runtime.host import RuntimeHost
from mediasense.volume import PathIdentity, observe_path_identity


def _identity(source: Path, mount: Path) -> PathIdentity:
    return PathIdentity(
        mount_root=mount,
        volume_identity="test-volume:portable",
        root_identity="test-root:portable",
        identity_strength="stable_volume",
    )


def _external_resolver(tmp_path: Path) -> tuple[DatasetResolver, Path, Path]:
    volume = tmp_path / "PhotoDisk"
    source = volume / "Photos"
    source.mkdir(parents=True)
    resolver = DatasetResolver(
        local_root=tmp_path / "local" / "datasets",
        mount_resolver=lambda path: volume,
        identity_observer=lambda path: _identity(path, volume),
        id_factory=lambda: "portable",
        clock=lambda: datetime(2026, 8, 31, tzinfo=UTC),
    )
    return resolver, volume, source


def test_external_dataset_is_created_on_volume_and_reopened(tmp_path: Path) -> None:
    resolver, volume, source = _external_resolver(tmp_path)

    created = resolver.open(source)
    reopened = resolver.open(source)

    assert created.tier is WorkspaceTier.EXTERNAL_VOLUME
    assert created.workspace.parent == volume / ".mediasense" / "datasets"
    assert created.manifest.dataset_ref == "dataset:portable"
    assert created.manifest.dataset_id == "portable"
    assert reopened.manifest.dataset_ref == created.manifest.dataset_ref
    assert reopened.workspace == created.workspace
    assert created.created is True
    assert reopened.created is False
    assert not (source / ".mediasense").exists()
    assert stat.S_IMODE(created.workspace.stat().st_mode) == 0o700
    assert stat.S_IMODE((created.workspace / "dataset.json").stat().st_mode) == 0o600


def test_explicit_workspace_has_priority_and_is_idempotent(tmp_path: Path) -> None:
    resolver, _volume, source = _external_resolver(tmp_path)
    explicit = tmp_path / "chosen-workspace"

    created = resolver.open(source, explicit_workspace=explicit)
    reopened = resolver.open(source, explicit_workspace=explicit)

    assert created.tier is WorkspaceTier.EXPLICIT
    assert created.workspace == explicit
    assert reopened.manifest.dataset_ref == created.manifest.dataset_ref
    assert reopened.created is False


def test_corrupt_external_match_does_not_fall_back_to_local(tmp_path: Path) -> None:
    resolver, volume, source = _external_resolver(tmp_path)
    key = hashlib.sha256(b"volume_relative\0Photos").hexdigest()[:24]
    workspace = volume / ".mediasense" / "datasets" / f"dataset-{key}"
    workspace.mkdir(parents=True)
    (workspace / "dataset.json").write_text("not json", encoding="utf-8")

    with pytest.raises(DatasetOpenError) as captured:
        resolver.open(source)

    assert captured.value.code == "manifest_invalid"
    assert not (tmp_path / "local" / "datasets").exists()


def test_existing_local_dataset_is_used_when_portable_state_is_absent(
    tmp_path: Path,
) -> None:
    resolver, _volume, source = _external_resolver(tmp_path)
    key = hashlib.sha256(b"volume_relative\0Photos\0test-volume:portable").hexdigest()[
        :24
    ]
    local_workspace = tmp_path / "local" / "datasets" / f"dataset-{key}"
    created = resolver.open(source, explicit_workspace=local_workspace)

    reopened = resolver.open(source)

    assert reopened.tier is WorkspaceTier.LOCAL
    assert reopened.workspace == local_workspace
    assert reopened.manifest.dataset_ref == created.manifest.dataset_ref


def test_existing_portable_dataset_has_priority_over_local_match(
    tmp_path: Path,
) -> None:
    resolver, volume, source = _external_resolver(tmp_path)
    portable_key = hashlib.sha256(b"volume_relative\0Photos").hexdigest()[:24]
    local_key = hashlib.sha256(
        b"volume_relative\0Photos\0test-volume:portable"
    ).hexdigest()[:24]
    local_workspace = tmp_path / "local" / "datasets" / f"dataset-{local_key}"
    local = resolver.open(source, explicit_workspace=local_workspace)
    portable_workspace = volume / ".mediasense" / "datasets" / f"dataset-{portable_key}"
    portable = resolver.open(source, explicit_workspace=portable_workspace)

    selected = resolver.open(source)

    assert local.workspace != portable.workspace
    assert selected.tier is WorkspaceTier.EXTERNAL_VOLUME
    assert selected.manifest.dataset_ref == portable.manifest.dataset_ref


def test_explicit_workspace_inside_source_is_refused(tmp_path: Path) -> None:
    source = tmp_path / "source"
    source.mkdir()
    resolver = DatasetResolver(local_root=tmp_path / "local")

    with pytest.raises(DatasetOpenError) as captured:
        resolver.open(source, explicit_workspace=source / ".mediasense")

    assert captured.value.code == "workspace_nested_in_source"
    assert not (source / ".mediasense").exists()


def test_newer_manifest_is_read_only_failure(tmp_path: Path) -> None:
    resolver, _volume, source = _external_resolver(tmp_path)
    opened = resolver.open(source)
    path = opened.workspace / "dataset.json"
    value = json.loads(path.read_text(encoding="utf-8"))
    value["format_version"] = 999
    path.write_text(json.dumps(value), encoding="utf-8")

    with pytest.raises(DatasetOpenError) as captured:
        resolver.open(source)

    assert captured.value.code == "manifest_newer"
    assert json.loads(path.read_text(encoding="utf-8"))["format_version"] == 999


def test_newer_component_store_is_refused_before_reopen_mutation(
    tmp_path: Path,
) -> None:
    resolver, _volume, source = _external_resolver(tmp_path)
    opened = resolver.open(source)
    database = opened.workspace / "precheck" / "work.sqlite3"
    with sqlite3.connect(database) as connection:
        connection.execute(
            "CREATE TABLE internal_schema (singleton INTEGER PRIMARY KEY, version INTEGER)"
        )
        connection.execute("INSERT INTO internal_schema VALUES (1, 999)")

    with pytest.raises(DatasetOpenError) as captured:
        resolver.open(source)

    assert captured.value.code == "store_newer"
    with sqlite3.connect(database) as connection:
        version = connection.execute(
            "SELECT version FROM internal_schema WHERE singleton = 1"
        ).fetchone()
    assert version == (999,)


def test_older_precheck_store_is_refused_without_migration(tmp_path: Path) -> None:
    resolver, _volume, source = _external_resolver(tmp_path)
    opened = resolver.open(source)
    manifest_path = opened.workspace / "dataset.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    manifest["stores"]["precheck"] = 16
    manifest_path.write_text(json.dumps(manifest), encoding="utf-8")
    database = opened.workspace / "precheck" / "work.sqlite3"
    with sqlite3.connect(database) as connection:
        connection.execute(
            "CREATE TABLE internal_schema (singleton INTEGER PRIMARY KEY, version INTEGER)"
        )
        connection.execute("INSERT INTO internal_schema VALUES (1, 16)")
    manifest_before = manifest_path.read_bytes()

    with pytest.raises(DatasetOpenError) as captured:
        resolver.open(source)

    assert captured.value.code == "store_unsupported"
    assert "version 16 has no supported migration" in str(captured.value)
    assert manifest_path.read_bytes() == manifest_before
    with sqlite3.connect(database) as connection:
        version = connection.execute(
            "SELECT version FROM internal_schema WHERE singleton = 1"
        ).fetchone()
    assert version == (16,)


def test_workspace_inspection_is_read_only(tmp_path: Path) -> None:
    resolver, _volume, source = _external_resolver(tmp_path)
    opened = resolver.open(source)
    before = (opened.workspace / "dataset.json").read_bytes()

    result = inspect_workspace(opened.workspace)

    assert result["dataset_ref"] == opened.manifest.dataset_ref
    assert (opened.workspace / "dataset.json").read_bytes() == before


@pytest.mark.parametrize(
    "component,relative_path",
    [
        ("precheck", "precheck/work.sqlite3"),
        ("plan", "plan/work.sqlite3"),
        ("geo", "geo/journal.sqlite3"),
        ("apply", "apply/work.sqlite3"),
    ],
)
def test_every_newer_component_store_blocks_before_mutation(
    tmp_path: Path, component: str, relative_path: str
) -> None:
    source = tmp_path / component / "source"
    source.mkdir(parents=True)
    workspace = tmp_path / component / "workspace"
    host = RuntimeHost()
    opened = host.open_dataset(str(source), str(workspace))
    assert opened["outcome"] == "ok"
    database = workspace / relative_path
    with sqlite3.connect(database) as connection:
        connection.execute("UPDATE internal_schema SET version = 999")

    resolver = DatasetResolver(local_root=tmp_path / "local")
    with pytest.raises(DatasetOpenError) as captured:
        resolver.open(source, explicit_workspace=workspace)

    assert captured.value.code == "store_newer"
    with sqlite3.connect(database) as connection:
        version = connection.execute(
            "SELECT version FROM internal_schema WHERE singleton = 1"
        ).fetchone()
    assert version == (999,)


def test_dataset_open_tool_reports_configuration_without_secret_values(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    source = tmp_path / "source"
    source.mkdir()
    monkeypatch.setenv("AMAP_API_KEY", "must-not-be-reported")
    tool = DatasetOpenTool(DatasetResolver(local_root=tmp_path / "local"))

    result = tool.handle({"source_root": str(source)})

    assert result["outcome"] == "ok"
    Draft202012Validator(
        load_contract("mediasense.dataset.open")["outputSchema"]
    ).validate(result)
    assert result["configuration"]["credentials"]["amap"] == "configured"
    assert "must-not-be-reported" not in json.dumps(result)


def test_portable_workspace_survives_mount_path_change(tmp_path: Path) -> None:
    first_mount = tmp_path / "PhotoDisk"
    source = first_mount / "Photos"
    source.mkdir(parents=True)
    resolver = DatasetResolver(
        local_root=tmp_path / "local",
        mount_resolver=lambda path: first_mount,
        identity_observer=lambda path: _identity(path, first_mount),
        id_factory=lambda: "portable",
    )
    first = resolver.open(source)

    second_mount = tmp_path / "RenamedPhotoDisk"
    first_mount.rename(second_mount)
    moved_source = second_mount / "Photos"
    moved_resolver = DatasetResolver(
        local_root=tmp_path / "other-local",
        mount_resolver=lambda path: second_mount,
        identity_observer=lambda path: _identity(path, second_mount),
    )
    reopened = moved_resolver.open(moved_source)

    assert reopened.created is False
    assert reopened.manifest.dataset_ref == first.manifest.dataset_ref
    assert reopened.workspace == (
        second_mount / ".mediasense" / "datasets" / first.workspace.name
    )


def test_portable_workspace_preserves_precheck_reuse_after_mount_move(
    tmp_path: Path,
) -> None:
    first_mount = tmp_path / "PhotoDisk"
    source = first_mount / "Photos"
    source.mkdir(parents=True)
    (source / "photo.jpg").write_bytes(b"photo")
    resolver = DatasetResolver(
        local_root=tmp_path / "local",
        mount_resolver=lambda path: first_mount,
        identity_observer=lambda path: _identity(path, first_mount),
    )
    opened = resolver.open(source)
    database = opened.workspace / "precheck" / "work.sqlite3"
    store = AccountingStore(database)
    store.register_dataset(opened.manifest.dataset_id)
    first_run = store.start_or_resume_run(opened.manifest.dataset_id, source)
    store.process_run(first_run)
    first_attachment = store.get_source_attachment(first_run)

    second_mount = tmp_path / "MovedPhotoDisk"
    first_mount.rename(second_mount)
    moved_source = second_mount / "Photos"
    reopened = DatasetResolver(
        local_root=tmp_path / "other-local",
        mount_resolver=lambda path: second_mount,
        identity_observer=lambda path: _identity(path, second_mount),
    ).open(moved_source)
    moved_store = AccountingStore(reopened.workspace / "precheck" / "work.sqlite3")
    second_run = moved_store.start_or_resume_run(
        reopened.manifest.dataset_id, moved_source
    )
    second_attachment = moved_store.get_source_attachment(second_run)

    assert second_attachment.reuse_domain == first_attachment.reuse_domain


def test_unsafe_new_external_workspace_falls_back_locally_with_warning(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    resolver, volume, source = _external_resolver(tmp_path)

    def probe(source_root: Path, workspace_root: Path):
        if volume / ".mediasense" in workspace_root.parents:
            raise UnsafeWorkspace("external locking is unavailable")
        return probe_source_attachment(source_root, workspace_root)

    monkeypatch.setattr("mediasense.runtime.dataset.probe_source_attachment", probe)

    opened = resolver.open(source)

    assert opened.tier is WorkspaceTier.LOCAL
    assert opened.warnings == ("portable_workspace_unavailable:workspace_unsafe",)


def test_volume_root_source_cannot_contain_its_own_workspace(tmp_path: Path) -> None:
    volume = tmp_path / "PhotoDisk"
    volume.mkdir()
    resolver = DatasetResolver(
        local_root=tmp_path / "local" / "datasets",
        mount_resolver=lambda path: volume,
        identity_observer=lambda path: _identity(path, volume),
    )

    opened = resolver.open(volume)

    assert opened.tier is WorkspaceTier.LOCAL
    assert opened.warnings == (
        "portable_workspace_unavailable:workspace_nested_in_source",
    )


def test_default_local_dataset_roots_follow_platform_conventions(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.delenv("XDG_DATA_HOME", raising=False)
    monkeypatch.delenv("MEDIASENSE_DATA_HOME", raising=False)
    assert default_local_dataset_root(platform_name="darwin", home=tmp_path) == (
        tmp_path / "Library" / "Application Support" / "MediaSense" / "datasets"
    )
    assert default_local_dataset_root(platform_name="linux", home=tmp_path) == (
        tmp_path / ".local" / "share" / "mediasense" / "datasets"
    )


def test_local_dataset_root_can_be_isolated_explicitly(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("MEDIASENSE_DATA_HOME", str(tmp_path / "state"))

    assert default_local_dataset_root() == tmp_path / "state" / "datasets"


def test_darwin_volume_uuid_provides_cross_mount_identity(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    source = tmp_path / "source"
    source.mkdir()
    payload = (
        b'<?xml version="1.0" encoding="UTF-8"?>'
        b'<plist version="1.0"><dict><key>VolumeUUID</key>'
        b"<string>ABC-123</string></dict></plist>"
    )

    def runner(*args: object, **kwargs: object) -> subprocess.CompletedProcess[bytes]:
        return subprocess.CompletedProcess([], 0, stdout=payload, stderr=b"")

    monkeypatch.setattr(
        "mediasense.volume.shutil.which", lambda name: "/usr/sbin/diskutil"
    )
    observed = observe_path_identity(source, platform_name="darwin", runner=runner)

    assert observed.volume_identity == "darwin-volume-uuid-v1:abc-123"
    assert observed.root_identity.startswith("darwin-volume-root-v1:abc-123:")
    assert observed.identity_strength == "stable_volume"
