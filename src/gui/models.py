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


@dataclass
class DivisionStandingEntry:
    """Represents a single team's row within a division ranking table.

    Fields intentionally generic to allow mapping from multiple league
    formats. Draws (D) may be zero for sports without draws.
    """

    position: int
    team_name: str
    matches_played: int
    wins: int
    draws: int
    losses: int
    goals_for: int | None = None  # or sets / points scored depending on sport
    goals_against: int | None = None
    points: int = 0
    recent_form: str | None = None  # e.g. "WWDLW" capped to last 5

    def differential(self) -> int | None:
        if self.goals_for is None or self.goals_against is None:
            return None
        return self.goals_for - self.goals_against


__all__ = [
    "TeamEntry",
    "PlayerEntry",
    "MatchDate",
    "TeamRosterBundle",
    "LoadResult",
    "PlayerHistoryEntry",
    "DivisionStandingEntry",
]
