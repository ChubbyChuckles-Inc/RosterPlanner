from __future__ import annotations

import sqlite3
from db.schema import apply_schema
from db.migration_manager import apply_pending_migrations
from db.integrity import run_integrity_checks


def _base_conn():
    conn = sqlite3.connect(":memory:")
    conn.execute("PRAGMA foreign_keys=ON")
    apply_schema(conn)
    apply_pending_migrations(conn)
    return conn


def test_integrity_clean_db():
    conn = _base_conn()
    try:
        issues = run_integrity_checks(conn)
        assert issues == []
    finally:
        conn.close()


def test_duplicate_team_name_same_season_detected():
    conn = _base_conn()
    cur = conn.cursor()
    # Insert two divisions same season
    cur.execute("INSERT INTO division(name, season) VALUES(?, ?)", ("Div A", 2025))
    cur.execute("INSERT INTO division(name, season) VALUES(?, ?)", ("Div B", 2025))
    cur.execute("SELECT division_id FROM division WHERE name='Div A'")
    div_a = cur.fetchone()[0]
    cur.execute("SELECT division_id FROM division WHERE name='Div B'")
    div_b = cur.fetchone()[0]
    # Same team name in both
    cur.execute(
        "INSERT INTO team(division_id, club_id, name) VALUES(?,?,?)",
        (div_a, None, "Team Shared"),
    )
    cur.execute(
        "INSERT INTO team(division_id, club_id, name) VALUES(?,?,?)",
        (div_b, None, "Team Shared"),
    )
    conn.commit()
    try:
        issues = run_integrity_checks(conn)
        assert any(i["category"] == "team_name_duplicate" for i in issues)
    finally:
        conn.close()
