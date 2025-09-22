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
from typing import Protocol, Iterable, Optional, runtime_checkable, Sequence
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


__all__ = [
    "DivisionRepository",
    "TeamRepository",
    "PlayerRepository",
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
]
