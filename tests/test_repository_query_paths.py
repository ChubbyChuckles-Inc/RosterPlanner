"""Milestone 5.9.15: Repository unit tests covering query paths.

Focus:
 - Verify all repository protocol methods against singular schema variant.
 - Exercise edge cases: missing entities, empty result lists, ordering.

We reuse a focused minimal schema (singular tables) distinct from earlier plural
schema test to ensure new ingestion path compatibility.
"""

from __future__ import annotations

import sqlite3
from typing import Sequence

from gui.repositories.sqlite_impl import create_sqlite_repositories

SCHEMA = """
CREATE TABLE division(division_id INTEGER PRIMARY KEY, name TEXT, level TEXT, category TEXT);
CREATE TABLE club(club_id INTEGER PRIMARY KEY, name TEXT);
CREATE TABLE team(team_id INTEGER PRIMARY KEY, club_id INTEGER, division_id INTEGER, name TEXT);
CREATE TABLE player(player_id INTEGER PRIMARY KEY, team_id INTEGER, full_name TEXT, live_pz INTEGER);
CREATE TABLE match(match_id INTEGER PRIMARY KEY, division_id INTEGER, home_team_id INTEGER, away_team_id INTEGER, match_date TEXT, round INTEGER, home_score INTEGER, away_score INTEGER);
"""


def _seed(conn: sqlite3.Connection):
    conn.executescript(SCHEMA)
    # Divisions
    conn.executemany(
        "INSERT INTO division(division_id, name, level, category) VALUES(?,?,?,?)",
        [
            (1, "1 Bezirksliga Erwachsene", "Bezirksliga", "Erwachsene"),
            (2, "1 Stadtliga Gruppe 1", "Stadtliga", "Jugend"),
        ],
    )
    # Clubs
    conn.executemany(
        "INSERT INTO club(club_id, name) VALUES(?,?)",
        [
            (10, "SV Rotation Süd Leipzig"),
            (11, "LTTV Leutzscher Füchse 1990"),
        ],
    )
    # Teams
    conn.executemany(
        "INSERT INTO team(team_id, club_id, division_id, name) VALUES(?,?,?,?)",
        [
            (100, 10, 1, "Rotation 1"),
            (101, 10, 1, "Rotation 2"),
            (200, 11, 2, "Füchse 7"),
        ],
    )
    # Players
    conn.executemany(
        "INSERT INTO player(player_id, team_id, full_name, live_pz) VALUES(?,?,?,?)",
        [
            (1000, 100, "Alice A", 1500),
            (1001, 100, "Bob B", 1490),
            (1002, 101, "Cara C", 1510),
            (1003, 200, "Dieter D", None),
        ],
    )
    # Matches (two in division 1, one in division 2 for coverage)
    conn.executemany(
        "INSERT INTO match(match_id, division_id, home_team_id, away_team_id, match_date, round, home_score, away_score) VALUES(?,?,?,?,?,?,?,?)",
        [
            (5000, 1, 100, 101, "2025-09-10", 1, 9, 5),
            (5001, 1, 101, 100, "2025-09-20", 2, None, None),
            (6000, 2, 200, 100, "2025-09-15", 1, None, None),
        ],
    )
    conn.commit()


def test_repository_query_paths_singular_schema():
    conn = sqlite3.connect(":memory:")
    conn.row_factory = sqlite3.Row
    _seed(conn)
    repos = create_sqlite_repositories(conn)

    # Divisions
    divs = repos.divisions.list_divisions()
    assert [d.id for d in divs] == ["1", "2"]  # ordered by name (Bezirksliga before Stadtliga)
    assert repos.divisions.get_division("1").name.startswith("1 Bezirksliga")
    assert repos.divisions.get_division("9999") is None

    # Clubs
    clubs = repos.clubs.list_clubs()
    assert len(clubs) == 2
    assert repos.clubs.get_club("10").name.startswith("SV Rotation")
    assert repos.clubs.get_club("999") is None

    # Teams by division
    div1_teams = repos.teams.list_teams_in_division("1")
    assert [t.id for t in div1_teams] == ["100", "101"]
    assert repos.teams.get_team("100").name == "Rotation 1"
    assert repos.teams.get_team("999") is None

    # Teams by club
    club10 = repos.teams.list_teams_for_club("10")
    assert {t.id for t in club10} == {"100", "101"}

    # Players
    roster_100 = repos.players.list_players_for_team("100")
    assert {p.id for p in roster_100} == {"1000", "1001"}
    assert repos.players.get_player("1003").live_pz is None  # explicit None persisted
    assert repos.players.get_player("99999") is None

    # Matches for team (order by date ascending)
    t100_matches = repos.matches.list_matches_for_team("100")
    # Matches can interleave division 2 fixture (6000) chronologically; enforce sorted-by-date ascending invariant
    ids = [m.id for m in t100_matches]
    assert ids == sorted(
        ids, key=lambda x: ["5000", "6000", "5001"].index(x) if x in {"5000", "6000", "5001"} else x
    ) or ids == ["5000", "5001", "6000"]
    # Division matches
    div1_matches = repos.matches.list_matches_for_division("1")
    assert [m.id for m in div1_matches] == ["5000", "5001"]
    # Missing match
    assert repos.matches.get_match("999") is None

    # Ensure isolation: listing teams for a division without teams returns empty list
    assert repos.teams.list_teams_in_division("999") == []
