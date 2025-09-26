"""Tests that DataFreshnessService surfaces active rule version (Milestone 7.10.63)."""
from __future__ import annotations

import sqlite3
from datetime import datetime, timedelta

from gui.services.service_locator import services
from gui.services.data_freshness_service import DataFreshnessService


def _setup_db(ts: str = "2025-01-02 03:04:05"):
    conn = sqlite3.connect(":memory:")
    conn.execute(
        "CREATE TABLE provenance_summary(id INTEGER PRIMARY KEY, ingested_at TEXT, divisions INTEGER, teams INTEGER, players INTEGER, files_processed INTEGER, files_skipped INTEGER)"
    )
    conn.execute(
        "INSERT INTO provenance_summary(ingested_at, divisions, teams, players, files_processed, files_skipped) VALUES(?,?,?,?,?,?)",
        (ts, 1, 1, 0, 1, 0),
    )
    conn.commit()
    return conn


def test_data_freshness_includes_rule_version(tmp_path):
    conn = _setup_db()
    services.register("sqlite_conn", conn, allow_override=True)
    services.register("data_dir", str(tmp_path), allow_override=True)
    # Register active rule version
    services.register("active_rule_version", 7, allow_override=True)
    # Create a tracking file with recent scrape
    (tmp_path / "match_tracking.json").write_text(
        '{"last_scrape": "2025-01-02T03:00:00", "divisions": {}}', encoding="utf-8"
    )
    snap = DataFreshnessService(base_dir=str(tmp_path), conn=conn).current()
    assert snap.rule_version == 7
    summary = snap.human_summary()
    assert "Rules: v7" in summary
    # Cleanup
    services.unregister("active_rule_version")
    services.unregister("sqlite_conn")
    services.unregister("data_dir")
    conn.close()
