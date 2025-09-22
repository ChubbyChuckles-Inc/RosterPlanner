"""Tests for ConsistencyValidationService (Milestone 5.9.20)."""

from __future__ import annotations

import sqlite3

from gui.services.consistency_validation_service import ConsistencyValidationService

SCHEMA = """
CREATE TABLE division(division_id INTEGER PRIMARY KEY, name TEXT, season INTEGER);
CREATE TABLE team(team_id INTEGER PRIMARY KEY, division_id INTEGER, name TEXT);
CREATE TABLE player(player_id INTEGER PRIMARY KEY, team_id INTEGER, full_name TEXT);
CREATE TABLE match(match_id INTEGER PRIMARY KEY, division_id INTEGER, home_team_id INTEGER, away_team_id INTEGER);
"""


def test_consistency_clean_case():
    conn = sqlite3.connect(":memory:")
    conn.executescript(SCHEMA)
    conn.execute("INSERT INTO division(division_id, name, season) VALUES(1,'Div A',2025)")
    conn.execute("INSERT INTO team(team_id, division_id, name) VALUES(10,1,'Team A')")
    conn.execute("INSERT INTO player(player_id, team_id, full_name) VALUES(100,10,'Alice')")
    conn.execute(
        "INSERT INTO match(match_id, division_id, home_team_id, away_team_id) VALUES(1000,1,10,10)"
    )
    result = ConsistencyValidationService(conn).validate()
    assert result.is_clean()
    assert result.stats["divisions"] == 1
    assert result.stats["teams"] == 1
    assert result.stats["players"] == 1
    assert result.stats["matches"] == 1


def test_consistency_orphans():
    conn = sqlite3.connect(":memory:")
    conn.executescript(SCHEMA)
    # Insert team referencing missing division
    conn.execute("INSERT INTO team(team_id, division_id, name) VALUES(10,99,'Ghost Team')")
    # Player referencing missing team
    conn.execute("INSERT INTO player(player_id, team_id, full_name) VALUES(100,77,'Ghost Player')")
    # Match referencing missing division and teams
    conn.execute(
        "INSERT INTO match(match_id, division_id, home_team_id, away_team_id) VALUES(1000,42,77,88)"
    )
    result = ConsistencyValidationService(conn).validate()
    assert not result.is_clean()
    # We expect all three orphan categories to be reported
    joined = " | ".join(result.errors)
    assert "Orphan teams" in joined
    assert "Orphan players" in joined
    assert "Orphan matches" in joined
