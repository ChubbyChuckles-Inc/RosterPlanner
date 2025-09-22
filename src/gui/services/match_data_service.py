"""MatchDataService (Milestone 5.9.10)

Provides upcoming and past match queries for a given team or division.
This wraps repository access and performs basic date segmentation and
sorting so views can simply present already-partitioned lists.

Future extensions:
- Date range filtering (custom start/end)
- Caching layer integration (Milestone 5.9.19)
- Performance metrics logging (Milestone P)
"""

from __future__ import annotations
from dataclasses import dataclass
from typing import List, Iterable, Tuple
import datetime as _dt
import sqlite3

from gui.repositories.sqlite_impl import create_sqlite_repositories
from gui.repositories.protocols import Match, TeamRepository, MatchRepository
from .service_locator import services

__all__ = ["MatchDataService", "TeamMatchSets", "DivisionMatchSets"]


@dataclass(frozen=True)
class TeamMatchSets:
    team_id: str
    past: List[Match]
    upcoming: List[Match]


@dataclass(frozen=True)
class DivisionMatchSets:
    division_id: str
    past: List[Match]
    upcoming: List[Match]


class MatchDataService:
    """High-level match querying & segmentation logic.

    Segmentation Rules:
    - Compare each match iso_date to today's date (local system date).
    - Matches with iso_date < today -> past; iso_date >= today -> upcoming
    - Sort past ascending by date then id (chronological), upcoming ascending.
    - Does not yet filter to team-specific home/away when using division set
      (caller can post-filter) except for team-level API which filters both
      home and away appearances.
    """

    def __init__(
        self,
        conn: sqlite3.Connection | None = None,
        teams_repo: TeamRepository | None = None,
        matches_repo: MatchRepository | None = None,
    ):
        self.conn = conn or services.try_get("sqlite_conn")
        self._teams_repo = teams_repo
        self._matches_repo = matches_repo

    def _repos(self):
        if self._teams_repo and self._matches_repo:
            return type(
                "_Injected", (), {"teams": self._teams_repo, "matches": self._matches_repo}
            )()
        if not self.conn:
            return None
        return create_sqlite_repositories(self.conn)

    @staticmethod
    def _segment(matches: Iterable[Match]) -> Tuple[List[Match], List[Match]]:
        today = _dt.date.today().isoformat()
        past: List[Match] = []
        upcoming: List[Match] = []
        for m in matches:
            if m.iso_date < today:
                past.append(m)
            else:
                upcoming.append(m)
        # Sort
        past.sort(key=lambda m: (m.iso_date, m.id))
        upcoming.sort(key=lambda m: (m.iso_date, m.id))
        return past, upcoming

    def team_matches(self, team_id: str) -> TeamMatchSets:
        repos = self._repos()
        if not repos:
            return TeamMatchSets(team_id, [], [])
        all_div_matches: List[Match] = []
        # Determine division via team lookup
        team = repos.teams.get_team(team_id)
        if not team:
            return TeamMatchSets(team_id, [], [])
        div_matches = repos.matches.list_matches_for_division(team.division_id)
        # Filter to matches involving team (home or away)
        for m in div_matches:
            if m.home_team_id == team_id or m.away_team_id == team_id:
                all_div_matches.append(m)
        past, upcoming = self._segment(all_div_matches)
        return TeamMatchSets(team_id, past, upcoming)

    def division_matches(self, division_id: str) -> DivisionMatchSets:
        repos = self._repos()
        if not repos:
            return DivisionMatchSets(division_id, [], [])
        matches = list(repos.matches.list_matches_for_division(division_id))
        past, upcoming = self._segment(matches)
        return DivisionMatchSets(division_id, past, upcoming)
