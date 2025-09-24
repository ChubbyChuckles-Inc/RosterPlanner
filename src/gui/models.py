"""GUI-facing lightweight models and adapters."""

from __future__ import annotations
from dataclasses import dataclass, field
from typing import List, Dict, Optional


@dataclass
class TeamEntry:
    team_id: str
    name: str  # raw team name (without club prefix)
    division: str
    club_name: str | None = None
    roster_pending: bool = False  # UI badge indicator when only placeholder/no real players yet

    @property
    def display_name(self) -> str:
        # Normalization rules:
        # 1. If name already contains a pipe ' | ' assume it is fully combined (legacy stored form) -> return as-is.
        # 2. Else if club present, format 'Club | TeamName'.
        # 3. Avoid duplication when club_name equals name (previous buggy state) – collapse to single occurrence.
        base_name = self.name.strip()
        if " | " in base_name or " – " in base_name:
            # Already combined (legacy pipe or new en dash form) -> return as-is
            disp = base_name
        elif self.club_name and self.club_name.strip():
            club = self.club_name.strip()
            if club == base_name:
                disp = club  # degenerate duplicate
            else:
                # New canonical separator: en dash with surrounding spaces for readability
                disp = f"{club} – {base_name}"
        else:
            disp = base_name
        if self.roster_pending:
            disp += " (Roster Pending)"
        return disp


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
