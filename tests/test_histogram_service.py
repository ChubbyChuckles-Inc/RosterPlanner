"""Tests for HistogramService (Milestone 6.3)."""

from __future__ import annotations

import sqlite3

from gui.services.service_locator import services
from gui.services.stats_histogram_service import HistogramService


def _seed(conn: sqlite3.Connection):
    cur = conn.cursor()
    cur.execute(
        "CREATE TABLE IF NOT EXISTS team(id TEXT PRIMARY KEY, name TEXT, division_id TEXT, club_id TEXT)"
    )
    cur.execute(
        "CREATE TABLE IF NOT EXISTS player(player_id TEXT PRIMARY KEY, full_name TEXT, team_id TEXT, live_pz INTEGER)"
    )
    cur.execute("INSERT INTO team(id,name,division_id,club_id) VALUES('T','Team','D',NULL)")
    # Players with diverse LivePZ values across bins
    for pid, lpz in [
        ("P1", 1510),
        ("P2", 1495),
        ("P3", 1622),
        ("P4", 1705),
        ("P5", None),  # missing value should be excluded
        ("P6", 1700),
    ]:
        cur.execute(
            "INSERT INTO player(player_id, full_name, team_id, live_pz) VALUES(?,?,?,?)",
            (pid, pid, "T", lpz),
        )
    conn.commit()


def test_histogram_basic():
    conn = sqlite3.connect(":memory:")
    _seed(conn)
    services.register("sqlite_conn", conn, allow_override=True)
    svc = HistogramService(conn)
    result = svc.build_team_live_pz_histogram("T", bin_size=100)
    # Expect bins covering 1400-1799 (since values from 1495 to 1705)
    labels = [b.label for b in result.bins]
    assert labels[0].startswith("1400")  # first bin 1400-1499
    mapping = result.as_dict()
    # Counts: 1495 (1), 1510 (1), 1622 (1), 1700 (1), 1705 (1)
    # Bins: 1400-1499 ->1, 1500-1599 ->1, 1600-1699 ->1, 1700-1799 ->2
    assert mapping.get("1400-1499") == 1
    assert mapping.get("1500-1599") == 1
    assert mapping.get("1600-1699") == 1
    assert mapping.get("1700-1799") == 2
    assert result.total_players == 6
    assert result.players_with_live_pz == 5


def test_histogram_empty_team():
    conn = sqlite3.connect(":memory:")
    cur = conn.cursor()
    cur.execute(
        "CREATE TABLE IF NOT EXISTS team(id TEXT PRIMARY KEY, name TEXT, division_id TEXT, club_id TEXT)"
    )
    cur.execute(
        "CREATE TABLE IF NOT EXISTS player(player_id TEXT PRIMARY KEY, full_name TEXT, team_id TEXT, live_pz INTEGER)"
    )
    cur.execute("INSERT INTO team(id,name,division_id,club_id) VALUES('X','Empty','D',NULL)")
    conn.commit()
    services.register("sqlite_conn", conn, allow_override=True)
    svc = HistogramService(conn)
    result = svc.build_team_live_pz_histogram("X")
    assert result.bins == [] and result.total_players == 0


def test_histogram_no_live_pz():
    conn = sqlite3.connect(":memory:")
    cur = conn.cursor()
    cur.execute(
        "CREATE TABLE IF NOT EXISTS team(id TEXT PRIMARY KEY, name TEXT, division_id TEXT, club_id TEXT)"
    )
    cur.execute(
        "CREATE TABLE IF NOT EXISTS player(player_id TEXT PRIMARY KEY, full_name TEXT, team_id TEXT, live_pz INTEGER)"
    )
    cur.execute("INSERT INTO team(id,name,division_id,club_id) VALUES('N','NoLPZ','D',NULL)")
    for pid in ["A", "B"]:
        cur.execute(
            "INSERT INTO player(player_id, full_name, team_id, live_pz) VALUES(?,?,?,?)",
            (pid, pid, "N", None),
        )
    conn.commit()
    services.register("sqlite_conn", conn, allow_override=True)
    svc = HistogramService(conn)
    result = svc.build_team_live_pz_histogram("N")
    assert result.bins == [] and result.players_with_live_pz == 0
