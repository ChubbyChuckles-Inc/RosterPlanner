"""Trend Detection Service (Milestone 6.6)

Provides rolling form (last N completed matches) for a team. This is a
lightweight analytical helper intended for feeding into future visualizations
and the stats dock. It leverages existing repositories via the registered
SQLite connection in the service locator.

Form Definition:
  win  -> 1.0
  draw -> 0.5 (defensive handling; rare in table tennis context)
  loss -> 0.0

Rolling form value at match i is the arithmetic mean of the outcome scores of
the previous `window` completed matches including match i (or fewer if fewer
completed matches exist yet).

Edge Cases:
 - Upcoming / incomplete matches (missing scores) are ignored.
 - If no completed matches -> empty list.
 - If only one completed match -> single entry with value 1/0.5/0.

Return Shape:
  List[TeamFormEntry] ordered chronologically by match date then id.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import List, Optional
import sqlite3

from .service_locator import services
from gui.repositories.sqlite_impl import create_sqlite_repositories

__all__ = ["TrendDetectionService", "TeamFormEntry"]


@dataclass(frozen=True)
class TeamFormEntry:
    match_id: str
    iso_date: str
    outcome_score: float  # 1 / 0.5 / 0
    rolling_form: float  # average over last window outcomes (including this match)


class TrendDetectionService:
    """Compute rolling form statistics for teams."""

    def __init__(self, default_window: int = 5):
        self.default_window = default_window

    def team_rolling_form(self, team_id: str, window: Optional[int] = None) -> List[TeamFormEntry]:
        window = window or self.default_window
        conn: sqlite3.Connection | None = services.try_get("sqlite_conn")
        if conn is None:
            return []
        repos = create_sqlite_repositories(conn)
        matches = [
            m
            for m in repos.matches.list_matches_for_team(team_id)
            if m.home_score is not None and m.away_score is not None
        ]
        if not matches:
            return []
        # Already ordered by date in repository; enforce deterministic secondary sort
        matches.sort(key=lambda m: (m.iso_date, m.id))
        entries: List[TeamFormEntry] = []
        outcome_buffer: List[float] = []
        for m in matches:
            # Determine perspective outcome
            if m.home_score == m.away_score:
                score = 0.5
            elif (m.home_team_id == team_id and m.home_score > m.away_score) or (
                m.away_team_id == team_id and m.away_score > m.home_score
            ):
                score = 1.0
            else:
                score = 0.0
            outcome_buffer.append(score)
            if len(outcome_buffer) > window:
                # Pop oldest
                outcome_buffer.pop(0)
            rolling = sum(outcome_buffer) / len(outcome_buffer)
            entries.append(
                TeamFormEntry(
                    match_id=m.id,
                    iso_date=m.iso_date,
                    outcome_score=score,
                    rolling_form=rolling,
                )
            )
        return entries
