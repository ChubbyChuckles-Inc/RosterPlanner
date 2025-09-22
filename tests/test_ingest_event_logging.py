"""Tests for structured ingest event logging (Milestone 5.9.24)."""

from __future__ import annotations

import sqlite3
import json
from pathlib import Path

from gui.services.ingestion_coordinator import IngestionCoordinator
from gui.services.service_locator import services


def _prepare_db() -> sqlite3.Connection:
    conn = sqlite3.connect(":memory:")
    conn.executescript(
        """
        CREATE TABLE division(division_id INTEGER PRIMARY KEY, name TEXT, season INTEGER, level TEXT, category TEXT);
        CREATE TABLE team(team_id INTEGER PRIMARY KEY, club_id INTEGER, division_id INTEGER, name TEXT);
        CREATE TABLE club(club_id INTEGER PRIMARY KEY, name TEXT);
        CREATE TABLE player(player_id INTEGER PRIMARY KEY, team_id INTEGER, full_name TEXT, live_pz INTEGER);
        CREATE TABLE division_ranking(division_id INTEGER, position INTEGER, team_name TEXT, points INTEGER, matches_played INTEGER, wins INTEGER, draws INTEGER, losses INTEGER, PRIMARY KEY(division_id, position));
        CREATE TABLE id_map(entity_type TEXT, source_key TEXT, assigned_id INTEGER PRIMARY KEY AUTOINCREMENT, UNIQUE(entity_type, source_key));
        CREATE TABLE provenance(path TEXT PRIMARY KEY, sha1 TEXT NOT NULL, last_ingested_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP, parser_version INTEGER DEFAULT 1);
        CREATE TABLE provenance_summary(id INTEGER PRIMARY KEY AUTOINCREMENT, ingested_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP, divisions INTEGER, teams INTEGER, players INTEGER, files_processed INTEGER, files_skipped INTEGER);
        """
    )
    return conn


def test_ingest_event_logging(tmp_path):
    # Enable logging
    services.register("ingest_event_logging", True, allow_override=True)
    # Create minimal HTML assets
    (tmp_path / "ranking_table_TestLiga.html").write_text("<html></html>", encoding="utf-8")
    (tmp_path / "team_roster_TestLiga_Team_A_111.html").write_text(
        "<html></html>", encoding="utf-8"
    )
    # Run ingestion
    conn = _prepare_db()
    coord = IngestionCoordinator(str(tmp_path), conn)
    summary = coord.run()
    assert summary.divisions_ingested == 1
    log_file = tmp_path / "ingest_events.jsonl"
    assert log_file.exists(), "Expected ingest_events.jsonl to be created"
    lines = [l for l in log_file.read_text(encoding="utf-8").splitlines() if l.strip()]
    # Expect at least start, division.start, division.success, ingest.complete
    events = [json.loads(l)["event"] for l in lines]
    assert "ingest.start" in events
    assert "division.start" in events
    assert "division.success" in events
    assert "ingest.complete" in events
