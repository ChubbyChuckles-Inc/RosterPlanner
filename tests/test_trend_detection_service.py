"""Tests for TrendDetectionService (Milestone 6.6)."""

from __future__ import annotations

import sqlite3
import pytest

from src.gui.services.trend_detection_service import TrendDetectionService
from src.gui.services.service_locator import services


@pytest.fixture(autouse=True)
def sqlite_conn():
    conn = sqlite3.connect(":memory:")
    conn.row_factory = sqlite3.Row
    conn.executescript(
        """
        CREATE TABLE division (division_id TEXT PRIMARY KEY, name TEXT, level TEXT, category TEXT);
        CREATE TABLE team (team_id TEXT PRIMARY KEY, name TEXT, division_id TEXT, club_id TEXT);
        CREATE TABLE player (player_id TEXT PRIMARY KEY, full_name TEXT, team_id TEXT, live_pz INTEGER);
        CREATE TABLE match (match_id TEXT PRIMARY KEY, division_id TEXT, home_team_id TEXT, away_team_id TEXT, match_date TEXT, round INTEGER, home_score INTEGER, away_score INTEGER);
        """
    )
    conn.execute("INSERT INTO division (division_id, name) VALUES (?,?)", ("d1", "Div"))
    teams = [("t1", "Alpha", "d1", None), ("t2", "Beta", "d1", None)]
    conn.executemany(
        "INSERT INTO team (team_id, name, division_id, club_id) VALUES (?,?,?,?)", teams
    )
    # Matches for t1 perspective: W, L, W, W, L, W
    matches = [
        ("m1", "d1", "t1", "t2", "2025-01-01", 1, 9, 5),  # W
        ("m2", "d1", "t2", "t1", "2025-01-05", 2, 9, 7),  # L
        ("m3", "d1", "t1", "t2", "2025-01-10", 3, 9, 6),  # W
        ("m4", "d1", "t2", "t1", "2025-01-15", 4, 7, 9),  # W (away)
        ("m5", "d1", "t1", "t2", "2025-01-20", 5, 5, 9),  # L
        ("m6", "d1", "t2", "t1", "2025-01-25", 6, 8, 9),  # W (away)
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


def test_trend_form_window_3():
    svc = TrendDetectionService(default_window=3)
    form = svc.team_rolling_form("t1")
    assert len(form) == 6
    # First entry: only first match -> rolling equals outcome (win=1)
    assert form[0].rolling_form == 1.0
    # Second entry: average of W (1) and L (0) -> 0.5
    assert abs(form[1].rolling_form - 0.5) < 1e-9
    # Third entry: W, L, W -> (1+0+1)/3 = 0.666...
    assert abs(form[2].rolling_form - (2 / 3)) < 1e-9
    # Fourth entry (window=3): last three outcomes L, W, W -> (0+1+1)/3 = 0.666...
    assert abs(form[3].rolling_form - (2 / 3)) < 1e-9
    # Fifth entry: outcomes W, W, L -> (1+1+0)/3 = 0.666...
    assert abs(form[4].rolling_form - (2 / 3)) < 1e-9
    # Sixth entry: outcomes W, L, W -> (1+0+1)/3 = 0.666...
    assert abs(form[5].rolling_form - (2 / 3)) < 1e-9


def test_trend_form_custom_window():
    svc = TrendDetectionService()
    form = svc.team_rolling_form("t1", window=2)
    # Rolling with window=2 should reflect last two outcomes
    # Outcome sequence (t1 perspective): W, L, W, W, L, W
    # Rolling window=2 progression (averages):
    # 1: [W] -> 1.0
    # 2: [W,L] -> 0.5
    # 3: [L,W] -> 0.5
    # 4: [W,W] -> 1.0
    # 5: [W,L] -> 0.5
    # 6: [L,W] -> 0.5
    assert len(form) == 6
    assert abs(form[0].rolling_form - 1.0) < 1e-9
    assert abs(form[1].rolling_form - 0.5) < 1e-9
    assert abs(form[2].rolling_form - 0.5) < 1e-9
    assert abs(form[3].rolling_form - 1.0) < 1e-9
    assert abs(form[4].rolling_form - 0.5) < 1e-9
    assert abs(form[5].rolling_form - 0.5) < 1e-9
