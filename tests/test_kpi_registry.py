"""Tests for KPI Registry (Milestone 6.1.1)."""

from __future__ import annotations

import sqlite3

from gui.services.service_locator import services
from gui.services.stats_service import StatsService
from gui.services.stats_kpi_registry import register_default_kpis, global_kpi_registry


def _seed(conn: sqlite3.Connection):
    c = conn.cursor()
    c.execute(
        "CREATE TABLE IF NOT EXISTS team(id TEXT PRIMARY KEY, name TEXT, division_id TEXT, club_id TEXT)"
    )
    c.execute(
        "CREATE TABLE IF NOT EXISTS player(player_id TEXT PRIMARY KEY, full_name TEXT, team_id TEXT, live_pz INTEGER)"
    )
    c.execute(
        "CREATE TABLE IF NOT EXISTS match(match_id INTEGER PRIMARY KEY AUTOINCREMENT, division_id TEXT, home_team_id TEXT, away_team_id TEXT, match_date TEXT, round INTEGER, home_score INTEGER, away_score INTEGER, status TEXT, match_number TEXT, match_time TEXT)"
    )
    c.execute("INSERT INTO team(id,name,division_id,club_id) VALUES('T1','Alpha','D1',NULL)")
    c.execute("INSERT INTO team(id,name,division_id,club_id) VALUES('T2','Beta','D1',NULL)")
    # Players (LivePZ values)
    for pid, lpz in [("P1", 1600), ("P2", 1500), ("P3", 1490), ("P4", 1400)]:
        c.execute(
            "INSERT INTO player(player_id, full_name, team_id, live_pz) VALUES(?,?,?,?)",
            (pid, pid, "T1", lpz),
        )
    # One completed win
    c.execute(
        "INSERT INTO match(division_id, home_team_id, away_team_id, match_date, round, home_score, away_score, status) VALUES(?,?,?,?,?,?,?,?)",
        ("D1", "T1", "T2", "2025-09-01", 1, 9, 3, "completed"),
    )
    conn.commit()


def test_default_kpis_compute():
    conn = sqlite3.connect(":memory:")
    _seed(conn)
    services.register("sqlite_conn", conn, allow_override=True)
    register_default_kpis()
    svc = StatsService(conn)
    win_pct = global_kpi_registry.compute("team.win_pct", svc, "T1")
    assert win_pct == 100.0  # one win -> 100%
    avg_top4 = global_kpi_registry.compute("team.avg_top4_lpz", svc, "T1")
    assert abs(avg_top4 - (1600 + 1500 + 1490 + 1400) / 4) < 1e-6
    participation = global_kpi_registry.compute("team.participation_uniform", svc, "T1")
    assert participation and isinstance(participation, dict)
    assert set(participation.values()) == {1.0}
