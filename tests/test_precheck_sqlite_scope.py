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
