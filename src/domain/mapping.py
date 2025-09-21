"""Utilities for mapping teams to clubs and merging datasets."""

from __future__ import annotations
from typing import Dict
from domain.models import Team


def merge_team_club_data(primary: Dict[str, Team], club_extra: Dict[str, Team]) -> Dict[str, Team]:
    merged = dict(primary)
    for team_id, team in club_extra.items():
        if team_id not in merged:
            team.is_additional_club_team = True
            merged[team_id] = team
    return merged
