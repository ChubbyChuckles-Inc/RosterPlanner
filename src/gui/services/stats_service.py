"""StatsService (Milestone 6.1)

Computes basic aggregated KPIs from repository data:
 - team_win_percentage(team_id)
 - average_top_live_pz(team_id, top_n=4)
 - player_participation_rate(team_id) (per player: matches played / matches total)

Design:
 - Read-only; depends on repositories exposed via `create_sqlite_repositories`.
 - Lightweight, stateless; callers may cache results if needed.
 - All methods tolerate missing/partial data (return None or empty structures).
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, List, Optional, Tuple
import sqlite3

from .service_locator import services
from gui.repositories.sqlite_impl import create_sqlite_repositories

__all__ = ["StatsService"]


@dataclass
class StatsService:
    conn: sqlite3.Connection | None = None

    def _ensure_conn(self) -> bool:
        if self.conn is not None:
            return True
        self.conn = services.try_get("sqlite_conn")
        return self.conn is not None

    # ---------------------------- Public KPI Methods ----------------------------
    def team_win_percentage(self, team_id: str) -> Optional[float]:
        """Return win percentage (0-1) for matches with recorded scores.

        A 'win' is defined as home_score > away_score for home team or vice versa.
        Draws (if ever present) count as 0.5 (currently table tennis likely has no draws).
        Returns None if no completed matches.
        """
        if not self._ensure_conn():
            return None
        repos = create_sqlite_repositories(self.conn)  # fresh lightweight wrapper
        matches = [
            m
            for m in repos.matches.list_matches_for_team(team_id)
            if m.home_score is not None and m.away_score is not None
        ]
        if not matches:
            return None
        wins = 0.0
        total = 0
        for m in matches:
            total += 1
            if m.home_score == m.away_score:
                wins += 0.5
            else:
                if m.home_team_id == team_id and m.home_score > m.away_score:
                    wins += 1
                elif m.away_team_id == team_id and m.away_score > m.home_score:
                    wins += 1
        return wins / total if total else None

    def average_top_live_pz(self, team_id: str, top_n: int = 4) -> Optional[float]:
        """Average LivePZ of top N players for a team.

        Returns None if no players have LivePZ recorded.
        """
        if not self._ensure_conn():
            return None
        repos = create_sqlite_repositories(self.conn)
        players = [p for p in repos.players.list_players_for_team(team_id) if p.live_pz is not None]
        if not players:
            return None
        players.sort(key=lambda p: p.live_pz or 0, reverse=True)
        subset = players[:top_n]
        return sum(p.live_pz for p in subset if p.live_pz is not None) / len(subset)

    def player_participation_rate(self, team_id: str) -> Dict[str, float]:
        """Estimate participation rate per player.

        Heuristic: if team has M matches with scores, a player is considered to
        have 'participated' if they appear in roster (we lack per-match lineup detail
        currently). This returns a uniform rate for all roster players until richer
        match lineup data is ingested.
        """
        if not self._ensure_conn():
            return {}
        repos = create_sqlite_repositories(self.conn)
        players = repos.players.list_players_for_team(team_id)
        if not players:
            return {}
        completed = [
            m
            for m in repos.matches.list_matches_for_team(team_id)
            if m.home_score is not None and m.away_score is not None
        ]
        total_completed = len(completed)
        if total_completed == 0:
            return {p.name: 0.0 for p in players}
        # Uniform placeholder assumption
        return {p.name: 1.0 for p in players}
