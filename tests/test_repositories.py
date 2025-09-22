from __future__ import annotations

import sqlite3
from db.schema import apply_schema
from db.migration_manager import apply_pending_migrations
from db.repositories import (
    DivisionRepository,
    TeamRepository,
    PlayerRepository,
)


def _conn():
    c = sqlite3.connect(":memory:")
    c.execute("PRAGMA foreign_keys=ON")
    apply_schema(c)
    apply_pending_migrations(c)
    return c


def test_division_upsert_idempotent():
    c = _conn()
    repo = DivisionRepository(c)
    did1 = repo.upsert("1. Liga", 2025)
    did2 = repo.upsert("1. Liga", 2025)
    assert did1 == did2
    all_divs = repo.list_all()
    assert len(all_divs) == 1


def test_team_and_player_upsert_and_update():
    c = _conn()
    div_repo = DivisionRepository(c)
    team_repo = TeamRepository(c)
    player_repo = PlayerRepository(c)
    did = div_repo.upsert("Test Division", 2025)
    tid = team_repo.upsert(did, "Alpha")
    pid_a = player_repo.upsert(tid, "Alice", 1500)
    pid_b = player_repo.upsert(tid, "Bob", 1400)
    # Idempotent re-upsert same values
    pid_a2 = player_repo.upsert(tid, "Alice", 1500)
    assert pid_a == pid_a2
    # Update Bob rating
    pid_b2 = player_repo.upsert(tid, "Bob", 1410)
    assert pid_b == pid_b2
    players = player_repo.list_by_team(tid)
    bob = next(p for p in players if p.full_name == "Bob")
    assert bob.live_pz == 1410


def test_player_search():
    c = _conn()
    div_repo = DivisionRepository(c)
    team_repo = TeamRepository(c)
    player_repo = PlayerRepository(c)
    did = div_repo.upsert("D", 2025)
    tid = team_repo.upsert(did, "Team")
    player_repo.upsert(tid, "Alice Alpha", 1000)
    player_repo.upsert(tid, "Bob Beta", 1100)
    hits = player_repo.search_by_name("alp")
    assert any("Alice" in p.full_name for p in hits)
