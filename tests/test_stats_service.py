"""Tests for StatsService basic KPI computations (Milestone 6.1)."""

from __future__ import annotations

import sqlite3
from gui.services.service_locator import services
from gui.services.stats_service import StatsService


def _seed(conn: sqlite3.Connection):
    cur = conn.cursor()
    # Minimal schema subset used in tests (guard against missing migrations);
    # use IF NOT EXISTS for idempotency.
    cur.execute(
        "CREATE TABLE IF NOT EXISTS team(id TEXT PRIMARY KEY, name TEXT, division_id TEXT, club_id TEXT)"
    )
    cur.execute(
        "CREATE TABLE IF NOT EXISTS player(player_id TEXT PRIMARY KEY, full_name TEXT, team_id TEXT, live_pz INTEGER)"
    )
    cur.execute(
        "CREATE TABLE IF NOT EXISTS match("
        "match_id INTEGER PRIMARY KEY AUTOINCREMENT,"
        "division_id TEXT, home_team_id TEXT, away_team_id TEXT, match_date TEXT,"
        "round INTEGER, home_score INTEGER, away_score INTEGER, status TEXT, match_number TEXT, match_time TEXT)"
    )
    # Teams
    cur.execute(
        "INSERT INTO team(id,name,division_id,club_id) VALUES(?,?,?,?)", ("T1", "Alpha", "D1", None)
    )
    cur.execute(
        "INSERT INTO team(id,name,division_id,club_id) VALUES(?,?,?,?)", ("T2", "Beta", "D1", None)
    )
    # Players
    for pid, name, lpz in [
        ("P1", "A One", 1500),
        ("P2", "A Two", 1480),
        ("P3", "A Three", 1400),
        ("P4", "A Four", 1350),
    ]:
        cur.execute(
            "INSERT INTO player(player_id, full_name, team_id, live_pz) VALUES(?,?,?,?)",
            (pid, name, "T1", lpz),
        )
    # Matches (two wins for T1, one loss)
    cur.execute(
        "INSERT INTO match(division_id, home_team_id, away_team_id, match_date, home_score, away_score, status) VALUES(?,?,?,?,?,?,?)",
        ("D1", "T1", "T2", "2025-09-01", 9, 3, "completed"),
    )
    cur.execute(
        "INSERT INTO match(division_id, home_team_id, away_team_id, match_date, home_score, away_score, status) VALUES(?,?,?,?,?,?,?)",
        ("D1", "T2", "T1", "2025-09-08", 4, 9, "completed"),
    )
    cur.execute(
        "INSERT INTO match(division_id, home_team_id, away_team_id, match_date, home_score, away_score, status) VALUES(?,?,?,?,?,?,?)",
        ("D1", "T2", "T1", "2025-09-15", 9, 6, "completed"),
    )
    conn.commit()


def test_team_win_percentage():
    conn = sqlite3.connect(":memory:")
    _seed(conn)
    services.register("sqlite_conn", conn, allow_override=True)
    svc = StatsService(conn)
    pct = svc.team_win_percentage("T1")
    assert pct is not None
    # T1: 2 wins out of 3 => 0.666...
    assert abs(pct - (2 / 3)) < 1e-6


def test_average_top_live_pz():
    conn = sqlite3.connect(":memory:")
    _seed(conn)
    services.register("sqlite_conn", conn, allow_override=True)
    svc = StatsService(conn)
    avg = svc.average_top_live_pz("T1", top_n=3)
    assert avg == (1500 + 1480 + 1400) / 3


def test_player_participation_rate():
    conn = sqlite3.connect(":memory:")
    _seed(conn)
    services.register("sqlite_conn", conn, allow_override=True)
    svc = StatsService(conn)
    rates = svc.player_participation_rate("T1")
    # Uniform placeholder; all players should have 1.0
    assert set(rates.values()) == {1.0}
    assert len(rates) == 4
