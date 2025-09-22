"""Tests for SQLite repository implementations (Milestone 5.9.2)."""

from __future__ import annotations

import sqlite3
from typing import Iterable

from gui.repositories import (
    create_sqlite_repositories,
    Division,
    Team,
    Player,
    Match,
    Club,
)

SCHEMA_SQL = """
CREATE TABLE divisions(id TEXT PRIMARY KEY, name TEXT NOT NULL, level TEXT, category TEXT);
CREATE TABLE clubs(id TEXT PRIMARY KEY, name TEXT NOT NULL);
CREATE TABLE teams(id TEXT PRIMARY KEY, name TEXT NOT NULL, division_id TEXT NOT NULL, club_id TEXT, FOREIGN KEY(division_id) REFERENCES divisions(id));
CREATE TABLE players(id TEXT PRIMARY KEY, name TEXT NOT NULL, team_id TEXT NOT NULL, live_pz INTEGER, FOREIGN KEY(team_id) REFERENCES teams(id));
CREATE TABLE matches(id TEXT PRIMARY KEY, division_id TEXT NOT NULL, home_team_id TEXT NOT NULL, away_team_id TEXT NOT NULL, iso_date TEXT NOT NULL, round INTEGER, home_score INTEGER, away_score INTEGER,
    FOREIGN KEY(division_id) REFERENCES divisions(id), FOREIGN KEY(home_team_id) REFERENCES teams(id), FOREIGN KEY(away_team_id) REFERENCES teams(id));
"""


def _exec_many(conn: sqlite3.Connection, statements: Iterable[str]):
    cur = conn.cursor()
    for stmt in statements:
        cur.execute(stmt)
    conn.commit()


def _prepare_db():
    conn = sqlite3.connect(":memory:")
    for statement in SCHEMA_SQL.strip().split(";\n"):
        s = statement.strip()
        if s:
            conn.execute(s)
    # Seed data
    conn.executemany(
        "INSERT INTO divisions(id, name, level, category) VALUES(?,?,?,?)",
        [("d1", "1. Stadtliga Gruppe 1", "Stadtliga", "Erwachsene")],
    )
    conn.executemany(
        "INSERT INTO clubs(id, name) VALUES(?,?)",
        [("c1", "LTTV Leutzscher Füchse 1990")],
    )
    conn.executemany(
        "INSERT INTO teams(id, name, division_id, club_id) VALUES(?,?,?,?)",
        [
            ("t1", "Füchse 1", "d1", "c1"),
            ("t2", "Füchse 2", "d1", "c1"),
        ],
    )
    conn.executemany(
        "INSERT INTO players(id, name, team_id, live_pz) VALUES(?,?,?,?)",
        [
            ("p1", "Alice", "t1", 1500),
            ("p2", "Bob", "t1", 1480),
            ("p3", "Cara", "t2", 1490),
        ],
    )
    conn.executemany(
        "INSERT INTO matches(id, division_id, home_team_id, away_team_id, iso_date, round, home_score, away_score) VALUES(?,?,?,?,?,?,?,?)",
        [
            ("m1", "d1", "t1", "t2", "2025-09-21", 1, None, None),
            ("m2", "d1", "t2", "t1", "2025-09-28", 2, None, None),
        ],
    )
    conn.commit()
    return conn


def test_sqlite_repositories_basic_queries():
    conn = _prepare_db()
    repos = create_sqlite_repositories(conn)

    # Divisions
    divisions = repos.divisions.list_divisions()
    assert len(divisions) == 1 and divisions[0].id == "d1"
    assert repos.divisions.get_division("d1").name.startswith("1. Stadtliga")

    # Clubs
    clubs = repos.clubs.list_clubs()
    assert len(clubs) == 1 and clubs[0].id == "c1"
    assert repos.clubs.get_club("c1").name.endswith("1990")

    # Teams
    teams = repos.teams.list_teams_in_division("d1")
    assert {t.id for t in teams} == {"t1", "t2"}
    assert repos.teams.get_team("t1").name == "Füchse 1"
    assert len(repos.teams.list_teams_for_club("c1")) == 2

    # Players
    roster = repos.players.list_players_for_team("t1")
    assert {p.id for p in roster} == {"p1", "p2"}
    assert repos.players.get_player("p3").live_pz == 1490

    # Matches
    matches_team_t1 = repos.matches.list_matches_for_team("t1")
    assert [m.id for m in matches_team_t1] == ["m1", "m2"]  # ordered by date
    matches_div = repos.matches.list_matches_for_division("d1")
    assert len(matches_div) == 2 and matches_div[0].id == "m1"
    assert repos.matches.get_match("m2").away_team_id == "t1"
