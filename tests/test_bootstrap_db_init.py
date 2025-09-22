import os
import sqlite3
import tempfile
from pathlib import Path

from gui.app.bootstrap import create_app


def test_bootstrap_creates_sqlite_schema(tmp_path: Path):
    data_dir = tmp_path / "data"
    data_dir.mkdir()
    ctx = create_app(headless=True, data_dir=str(data_dir))
    # Expect sqlite file created
    db_path = data_dir / "rosterplanner_gui.sqlite"
    assert db_path.exists(), "SQLite DB should be created on first bootstrap"
    # Check a core table exists (division) after auto schema init
    conn = sqlite3.connect(db_path)
    try:
        cur = conn.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='division'")
        assert cur.fetchone() is not None, "division table should exist after bootstrap schema init"
    finally:
        conn.close()
    # ctx ensures services registered
    assert ctx.services.get("sqlite_conn") is not None
