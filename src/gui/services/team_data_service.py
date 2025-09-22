"""TeamDataService (Milestone 5.9.6)

Bridges repository layer (SQLite-backed) to GUI bundle objects used by
`TeamDetailView` and `RosterLoadWorker`.

Current scope (incremental):
 - Fetch team entity by id (from teams repository) – if missing returns None
 - Fetch players for team (players repository)
 - Fetch matches for team (matches repository) and convert to simple match date list
 - Produce `TeamRosterBundle` (existing GUI model) with PlayerEntry + MatchDate objects

Defer advanced parsing / enriched attributes (e.g., LivePZ history, opponent names) to
later milestones once ingestion covers those tables fully.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Optional
import sqlite3

from gui.models import TeamEntry, PlayerEntry, MatchDate, TeamRosterBundle
from .service_locator import services
from gui.repositories.sqlite_impl import create_sqlite_repositories


@dataclass
class TeamDataService:
    """High-level data access for team roster details.

    This service is intentionally stateless beyond holding repository
    references; it can be recreated cheaply. It discovers (or lazily creates)
    repository instances on first use from a shared sqlite connection in
    the service locator. If the connection is absent, calls return None
    (allowing caller to fallback to legacy parsing path).
    """

    conn: sqlite3.Connection | None = None

    def _ensure_conn(self) -> bool:
        if self.conn is not None:
            return True
        self.conn = services.try_get("sqlite_conn")
        return self.conn is not None

    def load_team_bundle(self, team: TeamEntry) -> Optional[TeamRosterBundle]:
        """Load players + matches for a team via repositories.

        Returns None if required repositories/connection not available or
        team not found.
        """
        if not self._ensure_conn():  # sqlite not configured
            return None
        repos = create_sqlite_repositories(self.conn)  # lightweight wrapper
        # Confirm team exists (ingested)
        t = repos.teams.get_team(team.team_id)
        if t is None:
            return None
        players = [
            PlayerEntry(team_id=p.team_id, name=p.name, live_pz=p.live_pz)
            for p in repos.players.list_players_for_team(team.team_id)
        ]
        # Convert matches -> unique date display list (retain ordering)
        seen = set()
        match_dates: list[MatchDate] = []
        for m in repos.matches.list_matches_for_team(team.team_id):
            iso = m.iso_date
            if iso in seen:
                continue
            seen.add(iso)
            match_dates.append(MatchDate(iso_date=iso, display=iso, time=None))
        return TeamRosterBundle(team=team, players=players, match_dates=match_dates)


__all__ = ["TeamDataService"]
