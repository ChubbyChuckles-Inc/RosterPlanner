from __future__ import annotations

import sqlite3
from typing import Tuple

from db.schema import apply_schema
from db.migration_manager import apply_pending_migrations
from db.repositories import (
    DivisionRepository,
    TeamRepository,
    PlayerRepository,
    MatchRepository,
    AvailabilityRepository,
)


def make_conn() -> sqlite3.Connection:
    conn = sqlite3.connect(":memory:")
    conn.execute("PRAGMA foreign_keys=ON")
    apply_schema(conn)
    apply_pending_migrations(conn)
    return conn


def create_division(repo: DivisionRepository, name: str = "Test Div", season: int = 2025) -> int:
    return repo.upsert(name, season)


def create_team(
    div_repo: DivisionRepository, team_repo: TeamRepository, team_name: str = "Team A"
) -> Tuple[int, int]:
    did = create_division(div_repo)
    tid = team_repo.upsert(did, team_name)
    return did, tid


def create_player(
    player_repo: PlayerRepository, team_id: int, name: str = "Alice", live_pz: int = 1200
) -> int:
    return player_repo.upsert(team_id, name, live_pz)


__all__ = [
    "make_conn",
    "create_division",
    "create_team",
    "create_player",
]
