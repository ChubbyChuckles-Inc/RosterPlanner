"""Tests for StatsViewModel (Milestone 6 UI integration logic).

Ensures KPIs, time-series, and histogram combine coherently for a seeded team.
"""

from __future__ import annotations

import sqlite3

from gui.services.service_locator import services
from gui.viewmodels.stats_viewmodel import StatsViewModel


def _seed(conn: sqlite3.Connection):
    c = conn.cursor()
    c.execute(
        "CREATE TABLE IF NOT EXISTS team(team_id TEXT PRIMARY KEY, name TEXT, division_id TEXT, club_id TEXT)"
    )
    c.execute(
        "CREATE TABLE IF NOT EXISTS player(player_id TEXT PRIMARY KEY, full_name TEXT, team_id TEXT, live_pz INTEGER)"
    )
    c.execute(
        "CREATE TABLE IF NOT EXISTS match(match_id INTEGER PRIMARY KEY AUTOINCREMENT, division_id TEXT, home_team_id TEXT, away_team_id TEXT, match_date TEXT, round INTEGER, home_score INTEGER, away_score INTEGER, status TEXT, match_number TEXT, match_time TEXT)"
    )
    c.execute("INSERT INTO team(team_id,name,division_id,club_id) VALUES('T','Alpha','D',NULL)")
    c.execute("INSERT INTO team(team_id,name,division_id,club_id) VALUES('X','Beta','D',NULL)")
    # Players
    for i, lpz in enumerate([1500, 1490, 1400, 1300]):
        c.execute(
            "INSERT INTO player(player_id, full_name, team_id, live_pz) VALUES(?,?,?,?)",
            (f"P{i}", f"P{i}", "T", lpz),
        )
    # Matches (two wins, one loss)
    c.execute(
        "INSERT INTO match(division_id, home_team_id, away_team_id, match_date, home_score, away_score, status) VALUES(?,?,?,?,?,?,?)",
        ("D", "T", "X", "2025-09-01", 9, 3, "completed"),
    )
    c.execute(
        "INSERT INTO match(division_id, home_team_id, away_team_id, match_date, home_score, away_score, status) VALUES(?,?,?,?,?,?,?)",
        ("D", "X", "T", "2025-09-08", 4, 9, "completed"),
    )
    c.execute(
        "INSERT INTO match(division_id, home_team_id, away_team_id, match_date, home_score, away_score, status) VALUES(?,?,?,?,?,?,?)",
        ("D", "X", "T", "2025-09-15", 9, 6, "completed"),
    )
    conn.commit()


def test_stats_viewmodel_compose():
    conn = sqlite3.connect(":memory:")
    _seed(conn)
    services.register("sqlite_conn", conn, allow_override=True)
    vm = StatsViewModel()
    state = vm.load_for_team("T")
    kpi_map = vm.kpi_dict()
    assert "team.win_pct" in kpi_map and kpi_map["team.win_pct"] is not None
    assert any(row["cumulative_win_pct"] is not None for row in vm.timeseries_rows())
    hist = vm.histogram_counts()
    assert hist and sum(hist.values()) == 4
