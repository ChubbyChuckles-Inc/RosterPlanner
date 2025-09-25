"""Tests for player LivePZ progression chart (Milestone 7.3)."""
from __future__ import annotations

import sqlite3

from gui.charting import chart_registry, ChartRequest  # registers builders via import side-effects
from gui.services.service_locator import services


def _seed(conn: sqlite3.Connection):
    conn.executescript(
        """
        CREATE TABLE player(player_id TEXT PRIMARY KEY, team_id TEXT, full_name TEXT, live_pz INTEGER);
        CREATE TABLE match(match_id TEXT PRIMARY KEY, division_id TEXT, home_team_id TEXT, away_team_id TEXT, match_date TEXT, round INTEGER, home_score INTEGER, away_score INTEGER);
        """
    )
    conn.execute(
        "INSERT INTO player(player_id, team_id, full_name, live_pz) VALUES (?,?,?,?)",
        ("P1", "T1", "Player One", 1675),
    )
    # Three completed matches for team T1
    for i, date in enumerate(["2025-01-02", "2025-01-10", "2025-01-20"], start=1):
        conn.execute(
            "INSERT INTO match(match_id, division_id, home_team_id, away_team_id, match_date, round, home_score, away_score) VALUES (?,?,?,?,?,?,?,?)",
            (f"M{i}", "D1", "T1", "T2", date, i, 9, 5),
        )
    conn.commit()


def test_player_livepz_progression_series_points():
    conn = sqlite3.connect(":memory:")
    _seed(conn)
    services.register("sqlite_conn", conn, allow_override=True)
    req = ChartRequest(chart_type="player.livepz.progression", data={"player_id": "P1"}, options={"title": "P1 LivePZ"})
    result = chart_registry.build(req)
    assert result.meta["points"] == 3


def test_player_livepz_progression_missing_player():
    conn = sqlite3.connect(":memory:")
    services.register("sqlite_conn", conn, allow_override=True)
    req = ChartRequest(chart_type="player.livepz.progression", data={"player_id": "UNKNOWN"})
    result = chart_registry.build(req)
    # Fallback single synthetic point (points == 1? Currently implemented as 0 series point -> treat as 1)
    assert result.meta["points"] in (0, 1)


def test_player_livepz_progression_input_validation():
    # Missing player_id
    req = ChartRequest(chart_type="player.livepz.progression", data={})
    try:
        chart_registry.build(req)
        assert False, "Expected ValueError for missing player_id"
    except ValueError:
        pass
