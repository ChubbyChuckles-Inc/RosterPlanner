"""Tests for TimeSeriesBuilder (Milestone 6.2)."""

from __future__ import annotations

import sqlite3
from gui.services.service_locator import services
from gui.services.stats_timeseries_service import TimeSeriesBuilder


def _seed(conn: sqlite3.Connection):
    c = conn.cursor()
    c.execute(
        "CREATE TABLE IF NOT EXISTS team(id TEXT PRIMARY KEY, name TEXT, division_id TEXT, club_id TEXT)"
    )
    c.execute(
        "CREATE TABLE IF NOT EXISTS match(match_id INTEGER PRIMARY KEY AUTOINCREMENT, division_id TEXT, home_team_id TEXT, away_team_id TEXT, match_date TEXT, round INTEGER, home_score INTEGER, away_score INTEGER, status TEXT, match_number TEXT, match_time TEXT)"
    )
    c.execute("INSERT INTO team(id,name,division_id,club_id) VALUES('A','Alpha','D',NULL)")
    c.execute("INSERT INTO team(id,name,division_id,club_id) VALUES('B','Beta','D',NULL)")
    # Two match days; one completed win then an incomplete scheduled match
    c.execute(
        "INSERT INTO match(division_id, home_team_id, away_team_id, match_date, round, home_score, away_score, status) VALUES(?,?,?,?,?,?,?,?)",
        ("D", "A", "B", "2025-09-01", 1, 9, 3, "completed"),
    )
    c.execute(
        "INSERT INTO match(division_id, home_team_id, away_team_id, match_date, round, home_score, away_score, status) VALUES(?,?,?,?,?,?,?,?)",
        ("D", "B", "A", "2025-09-10", 2, None, None, "scheduled"),
    )
    conn.commit()


def test_timeseries_points():
    conn = sqlite3.connect(":memory:")
    _seed(conn)
    services.register("sqlite_conn", conn, allow_override=True)
    builder = TimeSeriesBuilder(conn)
    points = builder.build_team_match_timeseries("A")
    assert len(points) == 2
    first, second = points
    assert first.date == "2025-09-01"
    assert first.matches_played == 1 and first.completed == 1 and first.wins == 1
    assert abs(first.cumulative_win_pct - 1.0) < 1e-9
    assert second.date == "2025-09-10"
    assert second.completed == 0 and second.cumulative_win_pct == 1.0
