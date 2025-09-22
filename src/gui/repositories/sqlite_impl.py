"""SQLite-backed repository implementations (Milestone 5.9.2).

These implementations provide read-only accessors over the existing
database schema. They assume tables with (at least) the following columns:

divisions(id TEXT PRIMARY KEY, name TEXT, level TEXT NULL, category TEXT NULL)
clubs(id TEXT PRIMARY KEY, name TEXT)
teams(id TEXT PRIMARY KEY, name TEXT, division_id TEXT, club_id TEXT NULL)
players(id TEXT PRIMARY KEY, name TEXT, team_id TEXT, live_pz INTEGER NULL)
matches(id TEXT PRIMARY KEY, division_id TEXT, home_team_id TEXT, away_team_id TEXT,
        iso_date TEXT, round INTEGER NULL, home_score INTEGER NULL, away_score INTEGER NULL)

Queries are intentionally simple; optimization (indexes, joins) can come later
once profiling indicates need (Milestone 5.9.9 / 3.9). For now we fetch rows
with straightforward SELECT statements and map to immutable dataclasses.
"""

from __future__ import annotations

from dataclasses import dataclass
import sqlite3
from typing import Iterable, Sequence

from .protocols import (
    Division,
    Team,
    Player,
    Match,
    Club,
    DivisionRepository,
    TeamRepository,
    PlayerRepository,
    MatchRepository,
    ClubRepository,
)

__all__ = [
    "SqliteDivisionRepository",
    "SqliteTeamRepository",
    "SqlitePlayerRepository",
    "SqliteMatchRepository",
    "SqliteClubRepository",
    "create_sqlite_repositories",
]


def _row_to_division(row: sqlite3.Row) -> Division:
    return Division(id=row["id"], name=row["name"], level=row["level"], category=row["category"])


def _row_to_club(row: sqlite3.Row) -> Club:
    return Club(id=row["id"], name=row["name"])


def _row_to_team(row: sqlite3.Row) -> Team:
    return Team(
        id=row["id"], name=row["name"], division_id=row["division_id"], club_id=row["club_id"]
    )


def _row_to_player(row: sqlite3.Row) -> Player:
    return Player(id=row["id"], name=row["name"], team_id=row["team_id"], live_pz=row["live_pz"])


def _row_to_match(row: sqlite3.Row) -> Match:
    return Match(
        id=row["id"],
        division_id=row["division_id"],
        home_team_id=row["home_team_id"],
        away_team_id=row["away_team_id"],
        iso_date=row["iso_date"],
        round=row["round"],
        home_score=row["home_score"],
        away_score=row["away_score"],
    )


class _BaseRepo:
    def __init__(self, conn: sqlite3.Connection) -> None:
        self._conn = conn
        self._conn.row_factory = sqlite3.Row

    def _fetch_all(self, sql: str, *params) -> list[sqlite3.Row]:
        cur = self._conn.execute(sql, params)
        return list(cur.fetchall())

    def _fetch_one(self, sql: str, *params) -> sqlite3.Row | None:
        cur = self._conn.execute(sql, params)
        row = cur.fetchone()
        return row


class SqliteDivisionRepository(_BaseRepo, DivisionRepository):  # type: ignore[misc]
    def list_divisions(self) -> Sequence[Division]:
        return [
            _row_to_division(r)
            for r in self._fetch_all(
                "SELECT id, name, level, category FROM divisions ORDER BY name"
            )
        ]

    def get_division(self, division_id: str):  # Division | None
        row = self._fetch_one(
            "SELECT id, name, level, category FROM divisions WHERE id=?", division_id
        )
        return _row_to_division(row) if row else None


class SqliteClubRepository(_BaseRepo, ClubRepository):  # type: ignore[misc]
    def list_clubs(self):  # Sequence[Club]
        return [
            _row_to_club(r) for r in self._fetch_all("SELECT id, name FROM clubs ORDER BY name")
        ]

    def get_club(self, club_id: str):  # Club | None
        row = self._fetch_one("SELECT id, name FROM clubs WHERE id=?", club_id)
        return _row_to_club(row) if row else None


class SqliteTeamRepository(_BaseRepo, TeamRepository):  # type: ignore[misc]
    def list_teams_in_division(self, division_id: str):  # Sequence[Team]
        return [
            _row_to_team(r)
            for r in self._fetch_all(
                "SELECT id, name, division_id, club_id FROM teams WHERE division_id=? ORDER BY name",
                division_id,
            )
        ]

    def get_team(self, team_id: str):  # Team | None
        row = self._fetch_one(
            "SELECT id, name, division_id, club_id FROM teams WHERE id=?", team_id
        )
        return _row_to_team(row) if row else None

    def list_teams_for_club(self, club_id: str):  # Sequence[Team]
        return [
            _row_to_team(r)
            for r in self._fetch_all(
                "SELECT id, name, division_id, club_id FROM teams WHERE club_id=? ORDER BY name",
                club_id,
            )
        ]


class SqlitePlayerRepository(_BaseRepo, PlayerRepository):  # type: ignore[misc]
    def list_players_for_team(self, team_id: str):  # Sequence[Player]
        return [
            _row_to_player(r)
            for r in self._fetch_all(
                "SELECT id, name, team_id, live_pz FROM players WHERE team_id=? ORDER BY name",
                team_id,
            )
        ]

    def get_player(self, player_id: str):  # Player | None
        row = self._fetch_one(
            "SELECT id, name, team_id, live_pz FROM players WHERE id=?", player_id
        )
        return _row_to_player(row) if row else None


class SqliteMatchRepository(_BaseRepo, MatchRepository):  # type: ignore[misc]
    def list_matches_for_team(self, team_id: str):  # Sequence[Match]
        return [
            _row_to_match(r)
            for r in self._fetch_all(
                "SELECT id, division_id, home_team_id, away_team_id, iso_date, round, home_score, away_score FROM matches WHERE home_team_id=? OR away_team_id=? ORDER BY iso_date",
                team_id,
                team_id,
            )
        ]

    def list_matches_for_division(self, division_id: str):  # Sequence[Match]
        return [
            _row_to_match(r)
            for r in self._fetch_all(
                "SELECT id, division_id, home_team_id, away_team_id, iso_date, round, home_score, away_score FROM matches WHERE division_id=? ORDER BY iso_date",
                division_id,
            )
        ]

    def get_match(self, match_id: str):  # Match | None
        row = self._fetch_one(
            "SELECT id, division_id, home_team_id, away_team_id, iso_date, round, home_score, away_score FROM matches WHERE id=?",
            match_id,
        )
        return _row_to_match(row) if row else None


# Factory helper
@dataclass
class SqliteRepositories:
    divisions: SqliteDivisionRepository
    teams: SqliteTeamRepository
    players: SqlitePlayerRepository
    matches: SqliteMatchRepository
    clubs: SqliteClubRepository


def create_sqlite_repositories(conn: sqlite3.Connection) -> SqliteRepositories:
    """Create all SQLite repository instances sharing a single connection."""
    return SqliteRepositories(
        divisions=SqliteDivisionRepository(conn),
        teams=SqliteTeamRepository(conn),
        players=SqlitePlayerRepository(conn),
        matches=SqliteMatchRepository(conn),
        clubs=SqliteClubRepository(conn),
    )
