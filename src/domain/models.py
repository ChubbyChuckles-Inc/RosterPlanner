"""Domain models for roster planner scraping pipeline."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import List, Dict, Optional


@dataclass(slots=True)
class Team:
    id: str
    name: str
    division_name: Optional[str] = None
    club_id: Optional[str] = None
    is_additional_club_team: bool = False


@dataclass(slots=True)
class Division:
    name: str
    teams: List[Team] = field(default_factory=list)


@dataclass(slots=True)
class Match:
    team_id: str
    match_number: Optional[str]
    date: Optional[str]
    time: Optional[str]
    weekday: Optional[str]
    home_team: str
    guest_team: str
    home_score: Optional[int] = None
    guest_score: Optional[int] = None
    status: str = "upcoming"  # or "completed"


@dataclass(slots=True)
class Player:
    team_id: str
    name: str
    live_pz: Optional[int]


@dataclass(slots=True)
class Club:
    id: str
    teams: List[Team] = field(default_factory=list)


@dataclass(slots=True)
class TrackingState:
    last_scrape: Optional[datetime]
    divisions: Dict[str, Division]
    upcoming_matches: List[Match] = field(default_factory=list)

    @classmethod
    def empty(cls) -> "TrackingState":
        return cls(last_scrape=None, divisions={}, upcoming_matches=[])
