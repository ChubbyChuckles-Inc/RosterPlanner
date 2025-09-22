"""Test hash-based skipping in IngestionCoordinator (Milestone 5.9.4)."""

from __future__ import annotations

import sqlite3
from pathlib import Path
import time

from gui.services.ingestion_coordinator import IngestionCoordinator

SCHEMA_SQL = [
    "CREATE TABLE divisions(id TEXT PRIMARY KEY, name TEXT, level TEXT, category TEXT)",
    "CREATE TABLE clubs(id TEXT PRIMARY KEY, name TEXT)",
    "CREATE TABLE teams(id TEXT PRIMARY KEY, name TEXT, division_id TEXT, club_id TEXT)",
    "CREATE TABLE players(id TEXT PRIMARY KEY, name TEXT, team_id TEXT, live_pz INTEGER)",
    "CREATE TABLE matches(id TEXT PRIMARY KEY, division_id TEXT, home_team_id TEXT, away_team_id TEXT, iso_date TEXT, round INTEGER, home_score INTEGER, away_score INTEGER)",
]


def _prepare_db():
    conn = sqlite3.connect(":memory:")
    for stmt in SCHEMA_SQL:
        conn.execute(stmt)
    conn.commit()
    return conn


def _write(p: Path, name: str, content: str = "<html></html>"):
    (p / name).write_text(content, encoding="utf-8")


def test_hash_skip(tmp_path):
    _write(tmp_path, "ranking_table_1_Bezirksliga_Erwachsene.html", "<html>A</html>")
    _write(tmp_path, "team_roster_1_Bezirksliga_Erwachsene_Team_A_10.html", "<html>A1</html>")
    _write(tmp_path, "team_roster_1_Bezirksliga_Erwachsene_Team_B_11.html", "<html>B1</html>")

    conn = _prepare_db()
    coord = IngestionCoordinator(str(tmp_path), conn)

    first = coord.run()
    assert first.processed_files == 3
    assert first.skipped_files == 0

    # Second run should skip all (hash unchanged)
    second = coord.run()
    assert second.processed_files == 0
    assert second.skipped_files == 3

    # Modify one roster file -> only that file processed
    time.sleep(0.01)  # ensure timestamp difference on some FS
    _write(tmp_path, "team_roster_1_Bezirksliga_Erwachsene_Team_A_10.html", "<html>A2</html>")
    third = coord.run()
    assert third.processed_files == 1
    assert third.skipped_files == 2
