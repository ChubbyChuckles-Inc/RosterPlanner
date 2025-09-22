from __future__ import annotations

from db.repositories import (
    DivisionRepository,
    TeamRepository,
    PlayerRepository,
    MatchRepository,
    AvailabilityRepository,
)
from tests.factories import make_conn


def test_match_upsert_and_list():
    conn = make_conn()
    div_repo = DivisionRepository(conn)
    team_repo = TeamRepository(conn)
    match_repo = MatchRepository(conn)
    did = div_repo.upsert("Div", 2025)
    t1 = team_repo.upsert(did, "Team One")
    t2 = team_repo.upsert(did, "Team Two")
    mid1 = match_repo.upsert(did, t1, t2, "2025-09-01", status="scheduled")
    # Update with score
    mid2 = match_repo.upsert(
        did, t1, t2, "2025-09-01", status="completed", home_score=9, away_score=5
    )
    assert mid1 == mid2
    rows = match_repo.list_by_division(did)
    assert len(rows) == 1
    assert rows[0].home_score == 9 and rows[0].away_score == 5 and rows[0].status == "completed"


def test_availability_upsert_and_list():
    conn = make_conn()
    div_repo = DivisionRepository(conn)
    team_repo = TeamRepository(conn)
    player_repo = PlayerRepository(conn)
    avail_repo = AvailabilityRepository(conn)
    did = div_repo.upsert("Div", 2025)
    tid = team_repo.upsert(did, "Team One")
    pid = player_repo.upsert(tid, "Alice", 1500)
    a1 = avail_repo.upsert(pid, "2025-10-01", "available", confidence=90)
    a2 = avail_repo.upsert(pid, "2025-10-01", "unavailable", confidence=0, note="Injury")
    assert a1 == a2
    rows = avail_repo.list_for_player(pid)
    assert len(rows) == 1
    assert rows[0].status == "unavailable" and rows[0].note == "Injury"
