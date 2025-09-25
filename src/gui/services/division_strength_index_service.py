"""Division Strength Index Service (Milestone 6.5)

Computes an ELO-like aggregate rating per division using a simplified model:

 - Each team starts with a base rating derived from average top-N LivePZ (or a
   default baseline if insufficient data).
 - For each completed match (with scores), a delta is applied based on the
   expected score vs actual score using a logistic expectation and a modest K.
 - The division strength index is the average (or weighted average) of current
   team ratings; we expose both raw team ratings and the aggregate.

Design Constraints:
 - Read-only service; no persistence of ratings yet (stateless computation).
 - Deterministic: processing order is chronological by match date then id.
 - Lightweight: avoids external libraries; suitable for recomputation on demand.

Future Extensions (6.5.1 / later):
 - Persist rating history for graph endpoints.
 - Tune K-factor dynamically based on match importance / recency.
 - Incorporate margin of victory once reliable granular score detail exists.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, Optional
import math
import sqlite3

from .service_locator import services
from .stats_service import StatsService
from gui.repositories.sqlite_impl import create_sqlite_repositories

__all__ = [
    "DivisionStrengthIndexService",
    "DivisionStrengthResult",
    "DivisionStrengthHistoryEntry",
]


@dataclass(frozen=True)
class DivisionStrengthResult:
    division_id: str
    team_ratings: Dict[str, float]
    average_rating: float


@dataclass(frozen=True)
class DivisionStrengthHistoryEntry:
    """Snapshot of team ratings after processing a single match.

    Attributes:
        match_id: The match that produced this rating update.
        iso_date: Match date (YYYY-MM-DD) for chronological plotting.
        team_ratings: Ratings after applying the match result.
        average_rating: Division-wide average at this point in history.
    """

    match_id: str
    iso_date: str
    team_ratings: Dict[str, float]
    average_rating: float


class DivisionStrengthIndexService:
    """Compute per-division strength index via simplified ELO aggregation."""

    def __init__(
        self,
        base_rating: float = 1500.0,
        k_factor: float = 12.0,
        top_n_livepz: int = 4,
        fallback_livepz: float = 1500.0,
    ) -> None:
        self.base_rating = base_rating
        self.k_factor = k_factor
        self.top_n_livepz = top_n_livepz
        self.fallback_livepz = fallback_livepz
        self._stats = StatsService()

    def compute_division(self, division_id: str) -> Optional[DivisionStrengthResult]:
        conn: sqlite3.Connection | None = services.try_get("sqlite_conn")
        if conn is None:
            return None
        repos = create_sqlite_repositories(conn)
        teams = repos.teams.list_teams_in_division(division_id)
        if not teams:
            return None

        # Initialize team ratings using average top-N LivePZ where available
        ratings: Dict[str, float] = {}
        for t in teams:
            avg_livepz = self._stats.average_top_live_pz(t.id, top_n=self.top_n_livepz)
            ratings[t.id] = (
                self.base_rating
                if avg_livepz is None
                else self.base_rating + (avg_livepz - self.fallback_livepz) * 0.25
            )

        # Process completed matches
        matches = [
            m
            for m in repos.matches.list_matches_for_division(division_id)
            if m.home_score is not None and m.away_score is not None
        ]
        # Sort chronologically then by id for determinism
        matches.sort(key=lambda m: (m.iso_date, m.id))

        for m in matches:
            ra = ratings.get(m.home_team_id, self.base_rating)
            rb = ratings.get(m.away_team_id, self.base_rating)
            expected_a = self._expected_score(ra, rb)
            expected_b = 1.0 - expected_a
            # Actual score: win=1, loss=0, draw=0.5 (defensive handling)
            if m.home_score == m.away_score:
                sa, sb = 0.5, 0.5
            elif m.home_score > m.away_score:
                sa, sb = 1.0, 0.0
            else:
                sa, sb = 0.0, 1.0
            delta_a = self.k_factor * (sa - expected_a)
            delta_b = self.k_factor * (sb - expected_b)
            ratings[m.home_team_id] = ra + delta_a
            ratings[m.away_team_id] = rb + delta_b

        avg_rating = sum(ratings.values()) / len(ratings)
        return DivisionStrengthResult(
            division_id=division_id, team_ratings=ratings, average_rating=avg_rating
        )

    def compute_rating_history(self, division_id: str) -> list[DivisionStrengthHistoryEntry]:
        """Return chronological rating history snapshots for the division.

        Each snapshot represents the state immediately after applying a
        completed match. If no matches or repository unavailable, returns empty list.
        """
        conn: sqlite3.Connection | None = services.try_get("sqlite_conn")
        if conn is None:
            return []
        repos = create_sqlite_repositories(conn)
        teams = repos.teams.list_teams_in_division(division_id)
        if not teams:
            return []
        # Initialize ratings same as compute_division
        ratings: Dict[str, float] = {}
        for t in teams:
            avg_livepz = self._stats.average_top_live_pz(t.id, top_n=self.top_n_livepz)
            ratings[t.id] = (
                self.base_rating
                if avg_livepz is None
                else self.base_rating + (avg_livepz - self.fallback_livepz) * 0.25
            )
        matches = [
            m
            for m in repos.matches.list_matches_for_division(division_id)
            if m.home_score is not None and m.away_score is not None
        ]
        matches.sort(key=lambda m: (m.iso_date, m.id))
        history: list[DivisionStrengthHistoryEntry] = []
        for m in matches:
            ra = ratings.get(m.home_team_id, self.base_rating)
            rb = ratings.get(m.away_team_id, self.base_rating)
            expected_a = self._expected_score(ra, rb)
            expected_b = 1.0 - expected_a
            if m.home_score == m.away_score:
                sa, sb = 0.5, 0.5
            elif m.home_score > m.away_score:
                sa, sb = 1.0, 0.0
            else:
                sa, sb = 0.0, 1.0
            delta_a = self.k_factor * (sa - expected_a)
            delta_b = self.k_factor * (sb - expected_b)
            ratings[m.home_team_id] = ra + delta_a
            ratings[m.away_team_id] = rb + delta_b
            snapshot = DivisionStrengthHistoryEntry(
                match_id=m.id,
                iso_date=m.iso_date,
                team_ratings=dict(ratings),  # shallow copy for snapshot immutability
                average_rating=sum(ratings.values()) / len(ratings),
            )
            history.append(snapshot)
        return history

    # ---------------- Internal helpers ----------------
    def _expected_score(self, ra: float, rb: float) -> float:
        return 1.0 / (1.0 + 10 ** ((rb - ra) / 400))
