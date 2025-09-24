"""Histogram Service (Milestone 6.3)

Provides player strength (LivePZ) distribution histograms for a team.

Design goals:
 - Pure computation; no GUI dependencies.
 - Stable binning so repeated calls comparable even if team changes.
 - Handles missing / None LivePZ values by excluding them.
 - Returns both bin metadata and counts for easier charting later (Milestone 7).

API:
 - build_team_live_pz_histogram(team_id: str, *, bin_size: int = 100) -> HistogramResult

Assumptions:
 - LivePZ values are non-negative integers (as currently parsed). If floats appear later,
   they will still bin correctly using floor division.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import List, Dict, Tuple
import math
import sqlite3

from .service_locator import services
from gui.repositories.sqlite_impl import create_sqlite_repositories

__all__ = ["HistogramBin", "HistogramResult", "HistogramService"]


@dataclass(frozen=True)
class HistogramBin:
    lower: int  # inclusive
    upper: int  # exclusive
    count: int

    @property
    def label(self) -> str:
        return f"{self.lower}-{self.upper - 1}" if self.upper - self.lower > 1 else str(self.lower)


@dataclass(frozen=True)
class HistogramResult:
    team_id: str
    bin_size: int
    bins: List[HistogramBin]
    total_players: int
    players_with_live_pz: int

    def as_dict(self) -> Dict[str, int]:
        return {b.label: b.count for b in self.bins}


class HistogramService:
    def __init__(self, conn: sqlite3.Connection | None = None):
        self.conn = conn

    def _ensure_conn(self) -> bool:
        if self.conn is not None:
            return True
        self.conn = services.try_get("sqlite_conn")
        return self.conn is not None

    # ------------------------------------------------------------------
    def build_team_live_pz_histogram(self, team_id: str, *, bin_size: int = 100) -> HistogramResult:
        """Compute histogram of LivePZ values for players of a team.

        Returns empty result (zero bins) if no players or no LivePZ values.
        Bin sizing: values are grouped into [k*bin_size, (k+1)*bin_size) intervals.
        """
        if bin_size <= 0:
            raise ValueError("bin_size must be positive")
        if not self._ensure_conn():
            return HistogramResult(team_id, bin_size, [], 0, 0)
        repos = create_sqlite_repositories(self.conn)
        players = repos.players.list_players_for_team(team_id)
        total = len(players)
        values = [p.live_pz for p in players if p.live_pz is not None]
        if not values:
            return HistogramResult(team_id, bin_size, [], total, 0)
        # Determine min/max bins
        min_v = min(values)
        max_v = max(values)
        min_bin = (min_v // bin_size) * bin_size
        max_bin = (max_v // bin_size) * bin_size
        bins: List[HistogramBin] = []
        # Pre-build all bins to ensure continuity even if zero count
        current = min_bin
        counts: Dict[int, int] = {}
        for v in values:
            b = (v // bin_size) * bin_size
            counts[b] = counts.get(b, 0) + 1
        while current <= max_bin:
            upper = current + bin_size
            bins.append(HistogramBin(lower=current, upper=upper, count=counts.get(current, 0)))
            current += bin_size
        return HistogramResult(team_id, bin_size, bins, total, len(values))
