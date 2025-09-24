"""Time-Series Builder (Milestone 6.2)

Produces basic date-indexed match density & outcome aggregates for a team.

Current outputs (per team):
 - date (ISO YYYY-MM-DD)
 - matches_played: number of matches (scheduled or completed) that day
 - completed: number of matches with recorded scores that day
 - wins: count of wins that day (team perspective)
 - losses: count of losses that day
 - cumulative_win_pct: running win percentage across all completed matches up to that date

Design Notes:
 - Read-only; uses existing repositories through a fresh repository facade.
 - Availability coverage (future: integrate once availability schema implemented) is left as TODO.
 - Keeps computation in pure Python (dataset sizes expected small enough) – can be optimized later.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import List, Iterable, Optional
import sqlite3

from .service_locator import services
from gui.repositories.sqlite_impl import create_sqlite_repositories

__all__ = ["TimeSeriesPoint", "TimeSeriesBuilder"]


@dataclass(frozen=True)
class TimeSeriesPoint:
    date: str
    matches_played: int
    completed: int
    wins: int
    losses: int
    cumulative_win_pct: float | None


class TimeSeriesBuilder:
    def __init__(self, conn: sqlite3.Connection | None = None):
        self.conn = conn

    def _ensure_conn(self) -> bool:
        if self.conn is not None:
            return True
        self.conn = services.try_get("sqlite_conn")
        return self.conn is not None

    # ------------------------------------------------------------------
    def build_team_match_timeseries(self, team_id: str) -> List[TimeSeriesPoint]:
        """Construct a chronological time-series of match activity for a team.

        Returns an empty list if connection or matches absent.
        """
        if not self._ensure_conn():
            return []
        repos = create_sqlite_repositories(self.conn)
        matches = repos.matches.list_matches_for_team(team_id)
        if not matches:
            return []
        # Group matches by date preserving chronological order
        by_date: dict[str, list] = {}
        for m in matches:
            by_date.setdefault(m.iso_date, []).append(m)
        ordered_dates = sorted(by_date.keys())
        cumulative_completed = 0
        cumulative_wins = 0
        points: List[TimeSeriesPoint] = []
        for d in ordered_dates:
            day_matches = by_date[d]
            played = len(day_matches)
            completed = 0
            wins = 0
            losses = 0
            for m in day_matches:
                if m.home_score is not None and m.away_score is not None:
                    completed += 1
                    # Determine win/loss relative to team
                    if m.home_score == m.away_score:
                        # Draw scenario not expected; treat as neither (affects pct denominator only)
                        pass
                    else:
                        if m.home_team_id == team_id and m.home_score > m.away_score:
                            wins += 1
                        elif m.away_team_id == team_id and m.away_score > m.home_score:
                            wins += 1
                        else:
                            losses += 1
            cumulative_completed += completed
            cumulative_wins += wins
            if cumulative_completed:
                win_pct = cumulative_wins / cumulative_completed
            else:
                win_pct = None
            points.append(
                TimeSeriesPoint(
                    date=d,
                    matches_played=played,
                    completed=completed,
                    wins=wins,
                    losses=losses,
                    cumulative_win_pct=win_pct,
                )
            )
        return points
