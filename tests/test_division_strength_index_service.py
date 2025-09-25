"""Tests for DivisionStrengthIndexService (Milestone 6.5).

Uses an in-memory SQLite DB with minimal schema + seeded data to validate:
 - Ratings initialization from LivePZ averages
 - Rating adjustments after matches
 - Deterministic aggregate average
"""

from __future__ import annotations

import sqlite3
import pytest

from src.gui.services.division_strength_index_service import DivisionStrengthIndexService
from src.gui.services.service_locator import services


@pytest.fixture(autouse=True)
def sqlite_conn(monkeypatch):
    conn = sqlite3.connect(":memory:")
    conn.row_factory = sqlite3.Row
    # Minimal schema subset required
    conn.executescript(
        """
        CREATE TABLE division (division_id TEXT PRIMARY KEY, name TEXT, level TEXT, category TEXT);
        CREATE TABLE team (team_id TEXT PRIMARY KEY, name TEXT, division_id TEXT, club_id TEXT);
        CREATE TABLE player (player_id TEXT PRIMARY KEY, full_name TEXT, team_id TEXT, live_pz INTEGER);
        CREATE TABLE match (match_id TEXT PRIMARY KEY, division_id TEXT, home_team_id TEXT, away_team_id TEXT, match_date TEXT, round INTEGER, home_score INTEGER, away_score INTEGER);
        """
    )
    # Seed division
    conn.execute(
        "INSERT INTO division (division_id, name, level, category) VALUES (?,?,?,?)",
        ("d1", "Test Division", "Bezirksliga", "Erwachsene"),
    )
    # Seed teams
    teams = [("t1", "Alpha", "d1", None), ("t2", "Beta", "d1", None), ("t3", "Gamma", "d1", None)]
    conn.executemany(
        "INSERT INTO team (team_id, name, division_id, club_id) VALUES (?,?,?,?)", teams
    )
    # Seed players with varying LivePZ
    players = [
        ("p1", "A1", "t1", 1800),
        ("p2", "A2", "t1", 1750),
        ("p3", "A3", "t1", 1700),
        ("p4", "B1", "t2", 1650),
        ("p5", "B2", "t2", 1600),
        ("p6", "B3", "t2", 1550),
        ("p7", "C1", "t3", 1500),
        ("p8", "C2", "t3", 1490),
        ("p9", "C3", "t3", 1480),
    ]
    conn.executemany(
        "INSERT INTO player (player_id, full_name, team_id, live_pz) VALUES (?,?,?,?)", players
    )
    # Seed matches (chronological)
    matches = [
        ("m1", "d1", "t1", "t2", "2025-01-01", 1, 9, 5),  # t1 beats t2
        ("m2", "d1", "t2", "t3", "2025-01-08", 2, 9, 4),  # t2 beats t3
        ("m3", "d1", "t1", "t3", "2025-01-15", 3, 9, 3),  # t1 beats t3
    ]
    conn.executemany(
        "INSERT INTO match (match_id, division_id, home_team_id, away_team_id, match_date, round, home_score, away_score) VALUES (?,?,?,?,?,?,?,?)",
        matches,
    )
    services.register("sqlite_conn", conn)
    try:
        yield conn
    finally:
        services.unregister("sqlite_conn")
        conn.close()


def test_division_strength_index_basic():
    svc = DivisionStrengthIndexService()
    result = svc.compute_division("d1")
    assert result is not None
    assert result.division_id == "d1"
    # Expect three teams
    assert len(result.team_ratings) == 3
    # t1 should have highest rating after two wins
    r_t1 = result.team_ratings["t1"]
    r_t2 = result.team_ratings["t2"]
    r_t3 = result.team_ratings["t3"]
    assert r_t1 > r_t2 > r_t3
    # Average rating should be within reasonable band around base (1500)
    assert 1400 < result.average_rating < 1600


def test_division_strength_index_deterministic():
    svc1 = DivisionStrengthIndexService()
    svc2 = DivisionStrengthIndexService()
    r1 = svc1.compute_division("d1")
    r2 = svc2.compute_division("d1")
    assert r1 is not None and r2 is not None
    assert r1.team_ratings == r2.team_ratings
    assert abs(r1.average_rating - r2.average_rating) < 1e-9


def test_division_strength_rating_history():
    svc = DivisionStrengthIndexService()
    history = svc.compute_rating_history("d1")
    # Expect one snapshot per completed match
    assert len(history) == 3
    # Chronological ordering by iso_date
    dates = [h.iso_date for h in history]
    assert dates == sorted(dates)
    # Ratings evolve: first snapshot after m1 should differ from second
    assert history[0].team_ratings != history[1].team_ratings
    # Final snapshot ratings should match compute_division final state
    final = svc.compute_division("d1")
    assert final is not None
    assert final.team_ratings == history[-1].team_ratings
