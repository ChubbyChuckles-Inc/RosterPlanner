"""Repository layer (Milestone 3.5 / 3.5.1)

Defines typed repository interfaces separating read and write concerns.
Concrete implementations operate over a provided sqlite3.Connection.

Rationale:
 - Simplifies unit testing by allowing test doubles / in-memory DB.
 - Encapsulates SQL, keeping higher layers (viewmodels/services) decoupled.
 - Enables future swap to different persistence or caching decorators.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol, Optional, runtime_checkable, Sequence
import sqlite3


# ---- Domain DTOs (lightweight read models) ----


@dataclass(frozen=True)
class DivisionRow:
    division_id: int
    name: str
    season: int


@dataclass(frozen=True)
class TeamRow:
    team_id: int
    division_id: int
    name: str


@dataclass(frozen=True)
class PlayerRow:
    player_id: int
    team_id: int
    full_name: str
    live_pz: Optional[int]


@dataclass(frozen=True)
class MatchRow:
    match_id: int
    division_id: int
    home_team_id: int
    away_team_id: int
    match_date: str
    status: str
    home_score: Optional[int]
    away_score: Optional[int]


@dataclass(frozen=True)
class AvailabilityRow:
    availability_id: int
    player_id: int
    date: str
    status: str
    confidence: Optional[int]
    note: Optional[str]


@runtime_checkable
class DivisionReadRepository(Protocol):
    def get_by_id(self, division_id: int) -> Optional[DivisionRow]: ...  # pragma: no cover
    def list_all(self) -> Sequence[DivisionRow]: ...  # pragma: no cover


@runtime_checkable
class DivisionWriteRepository(Protocol):
    def upsert(self, name: str, season: int) -> int: ...  # pragma: no cover


@runtime_checkable
class TeamReadRepository(Protocol):
    def get_by_id(self, team_id: int) -> Optional[TeamRow]: ...  # pragma: no cover
    def list_by_division(self, division_id: int) -> Sequence[TeamRow]: ...  # pragma: no cover


@runtime_checkable
class TeamWriteRepository(Protocol):
    def upsert(self, division_id: int, name: str) -> int: ...  # pragma: no cover


@runtime_checkable
class PlayerReadRepository(Protocol):
    def list_by_team(self, team_id: int) -> Sequence[PlayerRow]: ...  # pragma: no cover
    def search_by_name(self, needle: str) -> Sequence[PlayerRow]: ...  # pragma: no cover


@runtime_checkable
class PlayerWriteRepository(Protocol):
    def upsert(
        self, team_id: int, full_name: str, live_pz: Optional[int]
    ) -> int: ...  # pragma: no cover


# ---- Concrete Implementations ----


class _BaseRepo:
    def __init__(self, conn: sqlite3.Connection):
        self._c = conn


class DivisionRepository(DivisionReadRepository, DivisionWriteRepository, _BaseRepo):
    def upsert(self, name: str, season: int) -> int:
        cur = self._c.cursor()
        cur.execute(
            "INSERT INTO division(name, season) VALUES(?, ?) ON CONFLICT(name, season) DO NOTHING",
            (name, season),
        )
        cur.execute(
            "SELECT division_id FROM division WHERE name=? AND season=?",
            (name, season),
        )
        return int(cur.fetchone()[0])

    def get_by_id(self, division_id: int) -> Optional[DivisionRow]:
        cur = self._c.cursor()
        cur.execute(
            "SELECT division_id, name, season FROM division WHERE division_id=?",
            (division_id,),
        )
        row = cur.fetchone()
        return DivisionRow(*row) if row else None

    def list_all(self) -> Sequence[DivisionRow]:
        cur = self._c.cursor()
        cur.execute("SELECT division_id, name, season FROM division ORDER BY name")
        return [DivisionRow(*r) for r in cur.fetchall()]


class TeamRepository(TeamReadRepository, TeamWriteRepository, _BaseRepo):
    def upsert(self, division_id: int, name: str) -> int:
        cur = self._c.cursor()
        cur.execute(
            "INSERT INTO team(division_id, club_id, name) VALUES(?, NULL, ?) ON CONFLICT(division_id, name) DO NOTHING",
            (division_id, name),
        )
        cur.execute(
            "SELECT team_id FROM team WHERE division_id=? AND name=?",
            (division_id, name),
        )
        return int(cur.fetchone()[0])

    def get_by_id(self, team_id: int) -> Optional[TeamRow]:
        cur = self._c.cursor()
        cur.execute(
            "SELECT team_id, division_id, name FROM team WHERE team_id=?",
            (team_id,),
        )
        row = cur.fetchone()
        return TeamRow(*row) if row else None

    def list_by_division(self, division_id: int) -> Sequence[TeamRow]:
        cur = self._c.cursor()
        cur.execute(
            "SELECT team_id, division_id, name FROM team WHERE division_id=? ORDER BY name",
            (division_id,),
        )
        return [TeamRow(*r) for r in cur.fetchall()]


class PlayerRepository(PlayerReadRepository, PlayerWriteRepository, _BaseRepo):
    def upsert(self, team_id: int, full_name: str, live_pz: Optional[int]) -> int:
        cur = self._c.cursor()
        cur.execute(
            "SELECT player_id, live_pz FROM player WHERE team_id=? AND full_name=?",
            (team_id, full_name),
        )
        row = cur.fetchone()
        if not row:
            cur.execute(
                "INSERT INTO player(team_id, full_name, live_pz) VALUES(?,?,?)",
                (team_id, full_name, live_pz),
            )
            return int(cur.lastrowid)
        player_id, existing_pz = row
        if existing_pz != live_pz:
            cur.execute(
                "UPDATE player SET live_pz=? WHERE player_id=?",
                (live_pz, player_id),
            )
        return int(player_id)

    def list_by_team(self, team_id: int):  # type: ignore[override]
        cur = self._c.cursor()
        cur.execute(
            "SELECT player_id, team_id, full_name, live_pz FROM player WHERE team_id=? ORDER BY full_name",
            (team_id,),
        )
        return [PlayerRow(*r) for r in cur.fetchall()]

    def search_by_name(self, needle: str):  # type: ignore[override]
        like = f"%{needle.lower()}%"
        cur = self._c.cursor()
        cur.execute(
            "SELECT player_id, team_id, full_name, live_pz FROM player WHERE lower(full_name) LIKE ?",
            (like,),
        )
        return [PlayerRow(*r) for r in cur.fetchall()]


class MatchRepository(_BaseRepo):
    """Match repository (combined read/write for now; can split later)."""

    def upsert(
        self,
        division_id: int,
        home_team_id: int,
        away_team_id: int,
        match_date: str,
        status: str = "scheduled",
        home_score: Optional[int] = None,
        away_score: Optional[int] = None,
    ) -> int:
        cur = self._c.cursor()
        cur.execute(
            """
            SELECT match_id, home_score, away_score, status FROM match
            WHERE division_id=? AND home_team_id=? AND away_team_id=? AND match_date=?
            """,
            (division_id, home_team_id, away_team_id, match_date),
        )
        row = cur.fetchone()
        if not row:
            cur.execute(
                """
                INSERT INTO match(division_id, home_team_id, away_team_id, match_date, status, home_score, away_score)
                VALUES(?,?,?,?,?,?,?)
                """,
                (
                    division_id,
                    home_team_id,
                    away_team_id,
                    match_date,
                    status,
                    home_score,
                    away_score,
                ),
            )
            return int(cur.lastrowid)
        mid, existing_home, existing_away, existing_status = row
        if existing_home != home_score or existing_away != away_score or existing_status != status:
            cur.execute(
                "UPDATE match SET status=?, home_score=?, away_score=? WHERE match_id=?",
                (status, home_score, away_score, mid),
            )
        return int(mid)

    def list_by_division(self, division_id: int) -> Sequence[MatchRow]:
        cur = self._c.cursor()
        cur.execute(
            """
            SELECT match_id, division_id, home_team_id, away_team_id, match_date, status, home_score, away_score
            FROM match WHERE division_id=? ORDER BY match_date
            """,
            (division_id,),
        )
        return [MatchRow(*r) for r in cur.fetchall()]


class AvailabilityRepository(_BaseRepo):
    """Availability repository with upsert semantics on (player_id, date)."""

    def upsert(
        self,
        player_id: int,
        date: str,
        status: str,
        confidence: Optional[int] = None,
        note: Optional[str] = None,
    ) -> int:
        cur = self._c.cursor()
        cur.execute(
            "SELECT availability_id, status, confidence, note FROM availability WHERE player_id=? AND date=?",
            (player_id, date),
        )
        row = cur.fetchone()
        if not row:
            cur.execute(
                "INSERT INTO availability(player_id, date, status, confidence, note) VALUES(?,?,?,?,?)",
                (player_id, date, status, confidence, note),
            )
            return int(cur.lastrowid)
        aid, existing_status, existing_conf, existing_note = row
        if existing_status != status or existing_conf != confidence or existing_note != note:
            cur.execute(
                "UPDATE availability SET status=?, confidence=?, note=? WHERE availability_id=?",
                (status, confidence, note, aid),
            )
        return int(aid)

    def list_for_player(self, player_id: int) -> Sequence[AvailabilityRow]:
        cur = self._c.cursor()
        cur.execute(
            """
            SELECT availability_id, player_id, date, status, confidence, note
            FROM availability WHERE player_id=? ORDER BY date
            """,
            (player_id,),
        )
        return [AvailabilityRow(*r) for r in cur.fetchall()]


__all__ = [
    "DivisionRepository",
    "TeamRepository",
    "PlayerRepository",
    "MatchRepository",
    "AvailabilityRepository",
    # Protocols
    "DivisionReadRepository",
    "DivisionWriteRepository",
    "TeamReadRepository",
    "TeamWriteRepository",
    "PlayerReadRepository",
    "PlayerWriteRepository",
    # DTOs
    "DivisionRow",
    "TeamRow",
    "PlayerRow",
    "MatchRow",
    "AvailabilityRow",
]
