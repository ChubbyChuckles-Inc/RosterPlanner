"""Tests for RosterCacheService (Milestone 5.9.19)."""

from __future__ import annotations

from gui.services.roster_cache_service import RosterCacheService
from gui.models import TeamRosterBundle, TeamEntry, PlayerEntry, MatchDate


def _bundle(team_id: str, players: int) -> TeamRosterBundle:
    team = TeamEntry(team_id=team_id, name=f"Team {team_id}", division="Div", club_name=None)
    plist = [PlayerEntry(team_id=team_id, name=f"P{i}") for i in range(players)]
    return TeamRosterBundle(
        team=team,
        players=plist,
        match_dates=[MatchDate(iso_date="2025-01-01", display="2025-01-01", time=None)],
    )


def test_lru_basic_eviction():
    cache = RosterCacheService(capacity=2)
    cache.put("A", _bundle("A", 1))
    cache.put("B", _bundle("B", 2))
    assert cache.get("A") is not None  # Access A -> now MRU order B,A
    cache.put("C", _bundle("C", 3))  # Should evict B
    assert cache.get("B") is None
    assert cache.get("A") is not None
    assert cache.get("C") is not None


def test_invalidate_and_clear():
    cache = RosterCacheService(capacity=3)
    cache.put("A", _bundle("A", 1))
    cache.put("B", _bundle("B", 1))
    cache.invalidate_team("A")
    assert cache.get("A") is None
    cache.clear()
    assert cache.get("B") is None
