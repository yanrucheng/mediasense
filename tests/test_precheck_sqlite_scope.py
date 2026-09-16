"""Producer-scoped connection reuse preserves transaction and thread isolation."""

from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
import sqlite3

import pytest

from mediasense.precheck._sqlite_scope import connect, connection_scope


def test_scope_commits_independently_and_closes_after_failure(tmp_path: Path) -> None:
    database = tmp_path / "scope.sqlite3"
    with pytest.raises(RuntimeError, match="producer failed"):
        with connection_scope(database):
            with connect(database) as first, first:
                first.execute("CREATE TABLE evidence (value TEXT)")
                first.execute("INSERT INTO evidence VALUES ('successful sibling')")
            with pytest.raises(ValueError):
                with connect(database) as second, second:
                    assert second is first
                    second.execute("INSERT INTO evidence VALUES ('failed sibling')")
                    raise ValueError("rollback only this operation")
            with sqlite3.connect(database) as observer:
                observer.execute("BEGIN IMMEDIATE")
                assert observer.execute("SELECT value FROM evidence").fetchall() == [
                    ("successful sibling",)
                ]
            raise RuntimeError("producer failed")
    with pytest.raises(sqlite3.ProgrammingError, match="closed"):
        first.execute("SELECT 1")
    with connect(database) as final:
        assert (
            final.execute("SELECT value FROM evidence").fetchone()[0]
            == "successful sibling"
        )


def test_nested_checkout_cannot_commit_its_callers_transaction(tmp_path: Path) -> None:
    database = tmp_path / "scope.sqlite3"
    with connection_scope(database):
        with connect(database) as outer:
            outer.execute("CREATE TABLE evidence (value TEXT)")
            outer.commit()
            outer.execute("BEGIN IMMEDIATE")
            outer.execute("INSERT INTO evidence VALUES ('uncommitted')")
            with connection_scope(database), connect(database) as nested, nested:
                assert nested is not outer
                assert (
                    nested.execute("SELECT count(*) FROM evidence").fetchone()[0] == 0
                )
            assert outer.in_transaction
        with connect(database) as final:
            assert not final.in_transaction
            assert final.execute("SELECT count(*) FROM evidence").fetchone()[0] == 0


def test_heartbeat_thread_has_its_own_connection_and_scope(tmp_path: Path) -> None:
    database = tmp_path / "scope.sqlite3"
    with connection_scope(database), connect(database) as main:

        def heartbeat():
            with connection_scope(database), connect(database) as connection:
                assert connection is not main
                return connection.execute("SELECT 1").fetchone()[0]

        with ThreadPoolExecutor(max_workers=1) as executor:
            assert executor.submit(heartbeat).result() == 1
        assert main.execute("SELECT 2").fetchone()[0] == 2


def test_timeout_is_preserved_and_read_snapshot_released(tmp_path: Path) -> None:
    from mediasense.precheck import AccountingStore
    from mediasense.precheck._run_sqlite import SQLiteRunStore

    database = tmp_path / "working.sqlite3"
    AccountingStore(database).register_dataset("test")
    store = SQLiteRunStore(database, sqlite_timeout=0.025)
    record, _ = store.start(
        {"request_id": "scope"}, dataset_ref="dataset:test", prior_result_ref=None
    )
    run_ref = record["run_ref"]
    with connection_scope(database):
        with store._connect() as first:
            assert first.execute("PRAGMA busy_timeout").fetchone()[0] == 25
        with connect(database) as default:
            assert default is not first
            assert default.execute("PRAGMA busy_timeout").fetchone()[0] == 30000
        assert store.observe(run_ref)["state"] == "running"
        assert not first.in_transaction

        def writer():
            with sqlite3.connect(database, timeout=0.025) as connection:
                connection.execute(
                    "UPDATE precheck_runs SET state = 'paused' WHERE run_ref = ?",
                    (run_ref,),
                )

        with ThreadPoolExecutor(max_workers=1) as executor:
            executor.submit(writer).result()
        assert store.observe(run_ref)["state"] == "paused"
        assert store.current_state(run_ref) == "paused"
        with store._connect() as reused:
            assert reused is first
