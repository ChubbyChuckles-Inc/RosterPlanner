from __future__ import annotations

import sqlite3
from pathlib import Path
from typing import List
import pytest

from db.rebuild import (
    rebuild_database_with_progress,
    RebuildProgressEvent,
    RebuildPhase,
)
from db.schema import apply_schema


def _failing_ingest(conn: sqlite3.Connection, root: Path, parser_version: str):  # noqa: D401
    raise RuntimeError("Simulated ingest failure")


def test_rebuild_progress_success(tmp_path: Path, monkeypatch):
    # Prepare simple file-backed DB with an initial table to prove destructive cycle.
    db_path = tmp_path / "app.sqlite"
    conn = sqlite3.connect(db_path)
    conn.execute("PRAGMA foreign_keys=ON")
    apply_schema(conn)
    conn.close()

    events: List[RebuildProgressEvent] = []

    def _cb(evt: RebuildProgressEvent):
        events.append(evt)

    # Use the data directory path itself (contains no HTML but ingest will no-op gracefully)
    conn2 = sqlite3.connect(db_path)
    conn2.execute("PRAGMA foreign_keys=ON")
    from db.ingest import ingest_path

    report = rebuild_database_with_progress(conn2, tmp_path, progress=_cb, ingest_func=ingest_path)
    assert report is not None
    phases = [e.phase for e in events]
    # Ensure at least these ordered phases occur
    assert phases[0] == RebuildPhase.START
    assert RebuildPhase.DROP in phases
    assert RebuildPhase.INGEST in phases
    assert phases[-1] == RebuildPhase.COMPLETE
    assert all(e.percent >= 0 for e in events)


def test_rebuild_progress_failure_rollback(tmp_path: Path):
    db_path = tmp_path / "app.sqlite"
    # Seed DB with a marker table data to verify it returns after rollback
    conn = sqlite3.connect(db_path)
    conn.execute("CREATE TABLE marker(id INTEGER PRIMARY KEY, note TEXT)")
    conn.execute("INSERT INTO marker(note) VALUES ('keep')")
    conn.commit()
    conn.close()

    # Capture original file bytes
    original_bytes = db_path.read_bytes()
    events: List[RebuildProgressEvent] = []

    def _cb(evt: RebuildProgressEvent):
        events.append(evt)

    conn2 = sqlite3.connect(db_path)
    conn2.execute("PRAGMA foreign_keys=ON")
    with pytest.raises(RuntimeError):
        rebuild_database_with_progress(conn2, tmp_path, progress=_cb, ingest_func=_failing_ingest)

    # After failure, original file should have been restored (bytes equality)
    restored_bytes = db_path.read_bytes()
    assert restored_bytes == original_bytes
    phases = [e.phase for e in events]
    assert RebuildPhase.ERROR in phases
    assert RebuildPhase.ROLLBACK in phases
