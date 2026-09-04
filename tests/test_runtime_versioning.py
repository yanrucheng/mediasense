from __future__ import annotations

import sqlite3
from pathlib import Path

import pytest

import mediasense
from mediasense.apply.preparation import _SCHEMA_VERSION as APPLY_SCHEMA_VERSION
from mediasense.capabilities.geo import GeoOperationJournal
from mediasense.capabilities.geo.journal import _SCHEMA_VERSION as GEO_SCHEMA_VERSION
from mediasense.plan._sqlite import SCHEMA_VERSION as PLAN_SCHEMA_VERSION
from mediasense.precheck._orchestrator import PrecheckExecutionConfig
from mediasense.precheck._working_schema import (
    SCHEMA_VERSION as PRECHECK_SCHEMA_VERSION,
)
from mediasense.runtime.versioning import DATASET_STORE_VERSIONS
from mediasense.runtime.versioning import application_version


def test_package_version_is_runtime_metadata() -> None:
    assert mediasense.__version__ == application_version() == "0.7.1"


def test_application_version_is_not_a_precheck_validity_input() -> None:
    configuration = PrecheckExecutionConfig().value()

    assert "application_version" not in configuration
    assert application_version() not in repr(configuration)


def test_dataset_store_versions_match_component_authorities() -> None:
    assert DATASET_STORE_VERSIONS == {
        "precheck": PRECHECK_SCHEMA_VERSION,
        "plan": PLAN_SCHEMA_VERSION,
        "geo": GEO_SCHEMA_VERSION,
        "apply": APPLY_SCHEMA_VERSION,
    }


def test_geo_journal_records_supported_schema_version(tmp_path: Path) -> None:
    database = tmp_path / "geo.sqlite3"

    GeoOperationJournal(database)

    with sqlite3.connect(database) as connection:
        version = connection.execute(
            "SELECT version FROM internal_schema WHERE singleton = 1"
        ).fetchone()
    assert version == (DATASET_STORE_VERSIONS["geo"],)


def test_geo_journal_refuses_newer_schema_without_writing(tmp_path: Path) -> None:
    database = tmp_path / "geo.sqlite3"
    GeoOperationJournal(database)
    with sqlite3.connect(database) as connection:
        connection.execute("UPDATE internal_schema SET version = 999")

    with pytest.raises(RuntimeError, match="unsupported Geo journal schema"):
        GeoOperationJournal(database)

    with sqlite3.connect(database) as connection:
        version = connection.execute(
            "SELECT version FROM internal_schema WHERE singleton = 1"
        ).fetchone()
    assert version == (999,)


def test_geo_journal_refuses_unversioned_existing_store(tmp_path: Path) -> None:
    database = tmp_path / "geo.sqlite3"
    with sqlite3.connect(database) as connection:
        connection.execute(
            "CREATE TABLE geo_operation_journal (request_id TEXT PRIMARY KEY)"
        )

    with pytest.raises(RuntimeError, match="unversioned"):
        GeoOperationJournal(database)
