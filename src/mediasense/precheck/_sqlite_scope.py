"""Thread-local connection reuse during one producer call, never a transaction.

Stores retain their own transaction boundaries. A scope only saves connection
setup; it owns neither durable state nor a lock across external work. Nested
operations and heartbeat threads cannot borrow an already checked-out connection.
"""

from __future__ import annotations

from contextlib import contextmanager
from dataclasses import dataclass
from pathlib import Path
import sqlite3
from threading import local
from typing import Iterator


@dataclass
class _ConnectionSlot:
    connection: sqlite3.Connection | None = None
    borrowed: bool = False


_thread = local()


@contextmanager
def connection_scope(database_path: Path) -> Iterator[None]:
    """Reuse idle connections only until the outermost same-thread scope exits."""

    key = Path(database_path).absolute()
    if not hasattr(_thread, "slots"):
        _thread.slots = {}
    slots: dict[Path, _ConnectionSlot] = _thread.slots
    if key in slots:
        yield
        return
    slot = slots[key] = _ConnectionSlot()
    try:
        yield
    finally:
        del slots[key]
        if slot.connection is not None:
            slot.connection.close()


@contextmanager
def connect(database_path: Path) -> Iterator[sqlite3.Connection]:
    key = Path(database_path).absolute()
    slot = getattr(_thread, "slots", {}).get(key)
    reusable = (
        slot is not None
        and not slot.borrowed
        and (slot.connection is None or not slot.connection.in_transaction)
    )
    connection = slot.connection if reusable else None
    if connection is None:
        connection = sqlite3.connect(database_path, timeout=30)
        connection.row_factory = sqlite3.Row
        connection.execute("PRAGMA foreign_keys = ON")
    if reusable:
        slot.connection = connection
        slot.borrowed = True
    try:
        yield connection
    finally:
        if reusable:
            # Just as close() did before reuse, discard any uncommitted work.
            # A producer scope must never become an implicit transaction.
            try:
                if connection.in_transaction:
                    connection.rollback()
            finally:
                slot.borrowed = False
        else:
            connection.close()
