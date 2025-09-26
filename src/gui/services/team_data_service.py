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
from .roster_cache_service import RosterCacheService
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
        """Load players + matches for a team via repositories with LRU caching.

        Cache Lookup:
            Attempts to retrieve an existing `TeamRosterBundle` from the
            `RosterCacheService` (if registered) before querying repositories.

        Cache Population:
            On successful repository fetch the bundle is inserted into the
            cache (if present). Missing repositories / connection or absent
            team returns None without caching.
        """
        # Attempt cache hit first
        cache: RosterCacheService | None = services.try_get("roster_cache")
        if cache is None:
            # Auto-register a default cache (lazy) to ensure caching works even if not pre-registered.
            try:
                cache = RosterCacheService()
                services.register("roster_cache", cache, allow_override=False)
            except Exception:
                cache = None
        if cache:
            # Align cache with current rule version (if any). A differing rule
            # version triggers a full clear inside ensure_rule_version.
            try:
                current_rule_version = services.try_get("active_rule_version")
            except Exception:  # pragma: no cover - defensive
                current_rule_version = None
            try:
                cache.ensure_rule_version(current_rule_version)  # type: ignore[attr-defined]
            except AttributeError:
                # Older cache instance without method (forward compatibility): ignore.
                pass
            cached = cache.get(team.team_id)
            if cached is not None:
                return cached

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
            # Repository exposes match_date as iso_date internally; support both attr names.
            iso = getattr(m, "iso_date", None) or getattr(m, "match_date", None)
            if iso is None:  # pragma: no cover - unexpected schema
                continue
            if iso in seen:
                continue
            seen.add(iso)
            # Derive a richer display: date [HH:MM] vs/opponent (score)
            # Determine opponent + home/away marker
            opponent = None
            venue = ""
            try:
                if m.home_team_id == team.team_id:
                    opponent = (
                        repos.teams.get_team(m.away_team_id).name
                        if repos.teams.get_team(m.away_team_id)
                        else None
                    )
                    venue = "vs"
                elif m.away_team_id == team.team_id:
                    opponent = (
                        repos.teams.get_team(m.home_team_id).name
                        if repos.teams.get_team(m.home_team_id)
                        else None
                    )
                    venue = "@"
            except Exception:
                opponent = None
            display = iso
            if opponent:
                display = f"{iso} {venue} {opponent}"
            if m.home_score is not None and m.away_score is not None:
                display = f"{display} ({m.home_score}:{m.away_score})"
            match_dates.append(MatchDate(iso_date=iso, display=display, time=None))
        bundle = TeamRosterBundle(team=team, players=players, match_dates=match_dates)
        if cache is None:
            cache = services.try_get("roster_cache")
        if cache:
            try:
                current_rule_version = services.try_get("active_rule_version")
                cache.ensure_rule_version(current_rule_version)  # type: ignore[attr-defined]
            except Exception:
                pass
            try:
                cache.put(team.team_id, bundle)
            except Exception:  # pragma: no cover
                pass
        return bundle

    # Invalidation helpers --------------------------------------
    @staticmethod
    def invalidate_team_cache(team_id: str) -> None:
        cache: RosterCacheService | None = services.try_get("roster_cache")
        if cache:
            cache.invalidate_team(team_id)

    @staticmethod
    def clear_cache() -> None:
        cache: RosterCacheService | None = services.try_get("roster_cache")
        if cache:
            cache.clear()


__all__ = ["TeamDataService"]
