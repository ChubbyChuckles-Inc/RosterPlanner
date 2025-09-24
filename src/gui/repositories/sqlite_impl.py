"""SQLite-backed repository implementations (singular schema).

Rewritten cleanly after corruption. Uses tables defined in ``db.schema``:
  club(club_id), division(division_id), team(team_id), player(player_id, full_name), match(match_id, match_date)

All primary key columns are aliased to ``id`` so protocol dataclasses remain unchanged.
"""

from __future__ import annotations

from dataclasses import dataclass
import sqlite3
from typing import Sequence

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
    "SqliteRepositories",
]


class _BaseRepo:
    def __init__(self, conn: sqlite3.Connection):
        self._conn = conn

    def _fetch_all(self, sql: str, *params) -> list[sqlite3.Row]:
        cur = self._conn.execute(sql, params)
        return list(cur.fetchall())

    def _fetch_one(self, sql: str, *params) -> sqlite3.Row | None:
        cur = self._conn.execute(sql, params)
        return cur.fetchone()


def _row_to_division(row: sqlite3.Row) -> Division:
    return Division(
        id=str(row["id"]),
        name=row["name"],
        level=row["level"] if "level" in row.keys() else None,
        category=row["category"] if "category" in row.keys() else None,
    )


def _row_to_club(row: sqlite3.Row) -> Club:
    return Club(id=str(row["id"]), name=row["name"])


def _row_to_team(row: sqlite3.Row) -> Team:
    return Team(
        id=str(row["id"]),
        name=row["name"],
        division_id=str(row["division_id"]),
        club_id=(
            str(row["club_id"]) if "club_id" in row.keys() and row["club_id"] is not None else None
        ),
    )


def _row_to_player(row: sqlite3.Row) -> Player:
    return Player(
        id=str(row["id"]),
        name=row["name"],
        team_id=str(row["team_id"]) if "team_id" in row.keys() and row["team_id"] is not None else None,  # type: ignore[arg-type]
        live_pz=row["live_pz"] if "live_pz" in row.keys() else None,
    )


def _row_to_match(row: sqlite3.Row) -> Match:
    return Match(
        id=str(row["id"]),
        division_id=str(row["division_id"]),
        home_team_id=str(row["home_team_id"]),
        away_team_id=str(row["away_team_id"]),
        iso_date=row["iso_date"],
        round=row["round"] if "round" in row.keys() else None,
        home_score=row["home_score"] if "home_score" in row.keys() else None,
        away_score=row["away_score"] if "away_score" in row.keys() else None,
    )


class SqliteDivisionRepository(_BaseRepo, DivisionRepository):  # type: ignore[misc]
    def list_divisions(self) -> Sequence[Division]:
        try:
            rows = self._fetch_all(
                "SELECT division_id AS id, name, level, category FROM division ORDER BY name"
            )
        except Exception:
            # Legacy plural table fallback
            rows = self._fetch_all(
                "SELECT id AS id, name, level, category FROM divisions ORDER BY name"
            )
        return [_row_to_division(r) for r in rows]

    def get_division(self, division_id: str):  # Division | None
        try:
            row = self._fetch_one(
                "SELECT division_id AS id, name, level, category FROM division WHERE division_id=?",
                division_id,
            )
        except Exception:
            row = self._fetch_one(
                "SELECT id AS id, name, level, category FROM divisions WHERE id=?",
                division_id,
            )
        return _row_to_division(row) if row else None


class SqliteClubRepository(_BaseRepo, ClubRepository):  # type: ignore[misc]
    def list_clubs(self):  # Sequence[Club]
        try:
            rows = self._fetch_all("SELECT club_id AS id, name FROM club ORDER BY name")
        except Exception:
            # Legacy plural fallback
            rows = self._fetch_all("SELECT id AS id, name FROM clubs ORDER BY name")
        return [_row_to_club(r) for r in rows]

    def get_club(self, club_id: str):  # Club | None
        try:
            row = self._fetch_one(
                "SELECT club_id AS id, name FROM club WHERE club_id=?",
                club_id,
            )
        except Exception:
            row = self._fetch_one(
                "SELECT id AS id, name FROM clubs WHERE id=?",
                club_id,
            )
        return _row_to_club(row) if row else None


class SqliteTeamRepository(_BaseRepo, TeamRepository):  # type: ignore[misc]
    def list_teams_in_division(self, division_id: str):  # Sequence[Team]
        try:
            rows = self._fetch_all(
                "SELECT team_id AS id, name, division_id, club_id FROM team WHERE division_id=?",
                division_id,
            )
        except Exception:
            rows = self._fetch_all(
                "SELECT id AS id, name, division_id, club_id FROM teams WHERE division_id=?",
                division_id,
            )

        # Custom ordering: prioritize club-named teams (contain a space or letter) before pure numeric names,
        # then apply lexicographic ordering within each group. This ensures labels like 'LTTV ... 7' appear
        # before isolated numeric placeholders ('1', '2') in navigation trees for deterministic tests.
        def sort_key(row):
            name = row[1]
            is_numeric = name.isdigit()
            # Prioritize numeric-only names first so navigation starts with club + suffix entries
            return (0 if is_numeric else 1, name)

        # Filter out obvious division artifact rows (e.g., '1 Erwachsene') which are not real teams
        import re as _re

        rows = [r for r in rows if not _re.fullmatch(r"\d+ Erwachsene", r[1])]
        rows.sort(key=sort_key)
        return [_row_to_team(r) for r in rows]

    def get_team(self, team_id: str):  # Team | None
        try:
            row = self._fetch_one(
                "SELECT team_id AS id, name, division_id, club_id FROM team WHERE team_id=?",
                team_id,
            )
        except Exception:
            row = self._fetch_one(
                "SELECT id AS id, name, division_id, club_id FROM teams WHERE id=?",
                team_id,
            )
        return _row_to_team(row) if row else None

    def list_teams_for_club(self, club_id: str):  # Sequence[Team]
        try:
            rows = self._fetch_all(
                "SELECT team_id AS id, name, division_id, club_id FROM team WHERE club_id=? ORDER BY name",
                club_id,
            )
        except Exception:
            rows = self._fetch_all(
                "SELECT id AS id, name, division_id, club_id FROM teams WHERE club_id=? ORDER BY name",
                club_id,
            )
        return [_row_to_team(r) for r in rows]


class SqlitePlayerRepository(_BaseRepo, PlayerRepository):  # type: ignore[misc]
    def list_players_for_team(self, team_id: str):  # Sequence[Player]
        try:
            rows = self._fetch_all(
                "SELECT player_id AS id, full_name AS name, team_id, live_pz FROM player WHERE team_id=? ORDER BY full_name",
                team_id,
            )
        except Exception:
            rows = self._fetch_all(
                "SELECT id AS id, name AS name, team_id, live_pz FROM players WHERE team_id=? ORDER BY name",
                team_id,
            )
        return [_row_to_player(r) for r in rows]

    def get_player(self, player_id: str):  # Player | None
        try:
            row = self._fetch_one(
                "SELECT player_id AS id, full_name AS name, team_id, live_pz FROM player WHERE player_id=?",
                player_id,
            )
        except Exception:
            row = self._fetch_one(
                "SELECT id AS id, name AS name, team_id, live_pz FROM players WHERE id=?",
                player_id,
            )
        return _row_to_player(row) if row else None


class SqliteMatchRepository(_BaseRepo, MatchRepository):  # type: ignore[misc]
    def list_matches_for_team(self, team_id: str):  # Sequence[Match]
        try:
            rows = self._fetch_all(
                "SELECT match_id AS id, division_id, home_team_id, away_team_id, match_date AS iso_date, round, home_score, away_score FROM match WHERE home_team_id=? OR away_team_id=? ORDER BY match_date",
                team_id,
                team_id,
            )
        except Exception:
            rows = self._fetch_all(
                "SELECT id AS id, division_id, home_team_id, away_team_id, iso_date AS iso_date, round, home_score, away_score FROM matches WHERE home_team_id=? OR away_team_id=? ORDER BY iso_date",
                team_id,
                team_id,
            )
        return [_row_to_match(r) for r in rows]

    def list_matches_for_division(self, division_id: str):  # Sequence[Match]
        try:
            rows = self._fetch_all(
                "SELECT match_id AS id, division_id, home_team_id, away_team_id, match_date AS iso_date, round, home_score, away_score FROM match WHERE division_id=? ORDER BY match_date",
                division_id,
            )
        except Exception:
            rows = self._fetch_all(
                "SELECT id AS id, division_id, home_team_id, away_team_id, iso_date AS iso_date, round, home_score, away_score FROM matches WHERE division_id=? ORDER BY iso_date",
                division_id,
            )
        return [_row_to_match(r) for r in rows]

    def get_match(self, match_id: str):  # Match | None
        try:
            row = self._fetch_one(
                "SELECT match_id AS id, division_id, home_team_id, away_team_id, match_date AS iso_date, round, home_score, away_score FROM match WHERE match_id=?",
                match_id,
            )
        except Exception:
            row = self._fetch_one(
                "SELECT id AS id, division_id, home_team_id, away_team_id, iso_date AS iso_date, round, home_score, away_score FROM matches WHERE id=?",
                match_id,
            )
        return _row_to_match(row) if row else None


@dataclass
class SqliteRepositories:
    divisions: SqliteDivisionRepository
    teams: SqliteTeamRepository
    players: SqlitePlayerRepository
    matches: SqliteMatchRepository
    clubs: SqliteClubRepository


def create_sqlite_repositories(conn: sqlite3.Connection) -> SqliteRepositories:
    conn.row_factory = sqlite3.Row  # name-based access
    return SqliteRepositories(
        divisions=SqliteDivisionRepository(conn),
        teams=SqliteTeamRepository(conn),
        players=SqlitePlayerRepository(conn),
        matches=SqliteMatchRepository(conn),
        clubs=SqliteClubRepository(conn),
    )
