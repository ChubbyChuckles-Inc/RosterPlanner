"""Build list of upcoming matches from parsed match data."""

from __future__ import annotations
from typing import Dict, List
from domain.models import Match, Team


def build_upcoming(matches_by_team: Dict[str, list[Match]], teams: dict[str, Team]) -> List[Match]:
    upcoming: List[Match] = []
    for team_id, matches in matches_by_team.items():
        for m in matches:
            if m.status == "upcoming":
                upcoming.append(m)
    return upcoming
