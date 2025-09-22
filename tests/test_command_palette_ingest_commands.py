"""Tests for ingestion & data freshness Command Palette actions (Milestone 5.9.22)."""

from __future__ import annotations

import sqlite3
from pathlib import Path
from datetime import datetime, timedelta
import json

from gui.services.command_registry import global_command_registry
from gui.services.service_locator import services


def _prepare_html(dir_path: Path):
    dir_path.mkdir(parents=True, exist_ok=True)
    (dir_path / "ranking_table_TestLiga.html").write_text(
        "<html><table><tr><td>1</td><td>Team A</td></tr></table></html>", encoding="utf-8"
    )
    (dir_path / "team_roster_TestLiga_Team_A_111.html").write_text(
        "<html></html>", encoding="utf-8"
    )


def _prepare_db() -> sqlite3.Connection:
    conn = sqlite3.connect(":memory:")
    conn.executescript(
        """
        CREATE TABLE division(division_id INTEGER PRIMARY KEY, name TEXT, season INTEGER, level TEXT, category TEXT);
        CREATE TABLE team(team_id INTEGER PRIMARY KEY, club_id INTEGER, division_id INTEGER, name TEXT);
        CREATE TABLE club(club_id INTEGER PRIMARY KEY, name TEXT);
        CREATE TABLE player(player_id INTEGER PRIMARY KEY, team_id INTEGER, full_name TEXT, live_pz INTEGER);
        CREATE TABLE id_map(entity_type TEXT, source_key TEXT, assigned_id INTEGER PRIMARY KEY AUTOINCREMENT, UNIQUE(entity_type, source_key));
        CREATE TABLE provenance(path TEXT PRIMARY KEY, sha1 TEXT NOT NULL, last_ingested_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP, parser_version INTEGER DEFAULT 1);
        CREATE TABLE provenance_summary(id INTEGER PRIMARY KEY AUTOINCREMENT, ingested_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP, divisions INTEGER, teams INTEGER, players INTEGER, files_processed INTEGER, files_skipped INTEGER);
        CREATE TABLE division_ranking(division_id INTEGER, position INTEGER, team_name TEXT, points INTEGER, matches_played INTEGER, wins INTEGER, draws INTEGER, losses INTEGER, PRIMARY KEY(division_id, position));
        """
    )
    return conn


def test_commands_register_and_execute(tmp_path, monkeypatch):
    # Arrange services
    data_dir = tmp_path / "data"
    _prepare_html(data_dir)
    conn = _prepare_db()
    services.register("data_dir", str(data_dir), allow_override=True)
    services.register("sqlite_conn", conn, allow_override=True)

    # Provide a fake tracking JSON for freshness (scrape timestamp 2 hours ago)
    tracking = {"last_scrape": (datetime.utcnow() - timedelta(hours=2)).isoformat()}
    (data_dir / "match_tracking.json").write_text(json.dumps(tracking), encoding="utf-8")

    # Import module (auto-register commands)
    import gui.services.ingest_commands  # noqa: F401

    assert global_command_registry.is_registered("ingest.force_reingest")
    assert global_command_registry.is_registered("data.show_freshness")

    # Execute force re-ingest
    ok, err = global_command_registry.execute("ingest.force_reingest")
    assert ok and err is None
    summary = services.get("last_ingest_summary")
    assert summary.divisions_ingested == 1
    assert summary.teams_ingested == 1

    # Execute freshness
    ok2, err2 = global_command_registry.execute("data.show_freshness")
    assert ok2 and err2 is None
    freshness = services.get("last_data_freshness")
    # Validate human summary contains key tokens
    hs = freshness.human_summary()
    assert "Scrape:" in hs and "Ingest:" in hs
