"""GUI-facing lightweight models and adapters."""

from __future__ import annotations
from dataclasses import dataclass, field
from typing import List, Dict, Optional


@dataclass
class TeamEntry:
    team_id: str
    name: str
    division: str


@dataclass
class PlayerEntry:
    team_id: str
    name: str
    live_pz: Optional[int] = None


@dataclass
class MatchDate:
    iso_date: str  # YYYY-MM-DD
    display: str  # e.g. 21.09.2025
    time: str | None = None


@dataclass
class TeamRosterBundle:
    team: TeamEntry
    players: List[PlayerEntry] = field(default_factory=list)
    match_dates: List[MatchDate] = field(default_factory=list)


@dataclass
class LoadResult:
    teams: List[TeamEntry]


@dataclass
class PlayerHistoryEntry:
    """Placeholder model representing a single historical performance entry.

    For now only stores date and LivePZ delta placeholder; future expansion
    could include opponent, match id, result, etc.
    """

    iso_date: str
    live_pz_delta: Optional[int] = None


__all__ = [
    "TeamEntry",
    "PlayerEntry",
    "MatchDate",
    "TeamRosterBundle",
    "LoadResult",
    "PlayerHistoryEntry",
]
