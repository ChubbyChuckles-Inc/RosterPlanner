"""DivisionDataService (Milestone 5.9.7)

Provides repository-backed computation of division standings replacing
the earlier placeholder row generator used by `MainWindow.open_division_table`.

Computation Strategy (incremental):
 - Fetch division (by id or name) and all teams within the division.
 - Fetch all matches for the division; only matches with non-null scores
   count toward standings (future: partial/live states could be handled).
 - Derive per-team aggregates: matches_played, wins, draws, losses,
   goals_for, goals_against, points.
 - Points system assumption (documented): Win = 2, Draw = 1, Loss = 0.
   This may be adjusted once domain-specific scoring rules are finalized.
 - Recent form = last up to 5 decided/played match outcomes (W/D/L)
   ordered from oldest->newest then *trimmed to* last 5 (GUI normalizer
   will also clamp if needed).
 - Teams with no played matches still appear (all zeros, no form).

Sorting: Primary = points desc, Secondary = goal differential desc (if available),
Tertiary = goals_for desc, Quaternary = team name asc. Positions are assigned
after sorting starting at 1.

Graceful Fallback: If repositories / sqlite connection not available the
`load_division_standings` method returns an empty list, allowing caller to
decide on any legacy placeholder behavior (currently just empty table).
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, List, Optional
import sqlite3

from gui.models import DivisionStandingEntry
from .service_locator import services
from gui.repositories.sqlite_impl import create_sqlite_repositories

WIN_POINTS = 2
DRAW_POINTS = 1
LOSS_POINTS = 0

__all__ = ["DivisionDataService", "WIN_POINTS", "DRAW_POINTS", "LOSS_POINTS"]


@dataclass
class _TeamAggregate:
    team_id: str
    name: str
    wins: int = 0
    draws: int = 0
    losses: int = 0
    goals_for: int = 0
    goals_against: int = 0
    form_tokens: List[str] | None = None  # accumulate chronological W/D/L

    def played(self) -> int:
        return self.wins + self.draws + self.losses

    def points(self) -> int:
        return self.wins * WIN_POINTS + self.draws * DRAW_POINTS + self.losses * LOSS_POINTS

    def recent_form(self) -> Optional[str]:
        if not self.form_tokens:
            return None
        # Keep all tokens; trimming to window handled either here (limit 5) or by normalizer.
        return "".join(self.form_tokens[-5:])


@dataclass
class DivisionDataService:
    conn: sqlite3.Connection | None = None

    def _ensure_conn(self) -> bool:
        if self.conn is not None:
            return True
        self.conn = services.try_get("sqlite_conn")
        return self.conn is not None

    def load_division_standings(self, division_identifier: str) -> List[DivisionStandingEntry]:
        """Return computed standings for a division.

        The `division_identifier` may be either the division *id* or the
        exact division *name*. We first attempt id lookup; if not found we
        fall back to name matching (case-sensitive, then case-insensitive).
        """
        if not self._ensure_conn():  # no DB available
            return []
        repos = create_sqlite_repositories(self.conn)

        # Resolve division
        division = repos.divisions.get_division(division_identifier)
        if division is None:
            # attempt name match
            all_divs = repos.divisions.list_divisions()
            for d in all_divs:
                if d.name == division_identifier:
                    division = d
                    break
            if division is None:
                # case-insensitive
                lowered = division_identifier.lower()
                for d in all_divs:
                    if d.name.lower() == lowered:
                        division = d
                        break
        if division is None:
            return []

        teams = list(repos.teams.list_teams_in_division(division.id))
        # Prepare aggregates keyed by team id
        aggregates: Dict[str, _TeamAggregate] = {
            t.id: _TeamAggregate(team_id=t.id, name=t.name) for t in teams
        }
        # Index for reverse lookup name if needed later
        if not aggregates:
            return []

        matches = list(repos.matches.list_matches_for_division(division.id))
        # Sort matches chronologically for form computation
        matches.sort(key=lambda m: (m.iso_date, m.id))

        for m in matches:
            # Only count if both scores present (played match)
            if m.home_score is None or m.away_score is None:
                continue
            home = aggregates.get(m.home_team_id)
            away = aggregates.get(m.away_team_id)
            if not home or not away:
                continue  # ignore matches with teams outside this division
            # Goals
            home.goals_for += m.home_score
            home.goals_against += m.away_score
            away.goals_for += m.away_score
            away.goals_against += m.home_score
            # Outcome
            if m.home_score > m.away_score:
                home.wins += 1
                away.losses += 1
                home.form_tokens = (home.form_tokens or []) + ["W"]
                away.form_tokens = (away.form_tokens or []) + ["L"]
            elif m.away_score > m.home_score:
                away.wins += 1
                home.losses += 1
                away.form_tokens = (away.form_tokens or []) + ["W"]
                home.form_tokens = (home.form_tokens or []) + ["L"]
            else:  # draw
                home.draws += 1
                away.draws += 1
                home.form_tokens = (home.form_tokens or []) + ["D"]
                away.form_tokens = (away.form_tokens or []) + ["D"]

        # Build standing entries
        entries: List[DivisionStandingEntry] = []
        for agg in aggregates.values():
            entries.append(
                DivisionStandingEntry(
                    position=0,  # fill later
                    team_name=agg.name,
                    matches_played=agg.played(),
                    wins=agg.wins,
                    draws=agg.draws,
                    losses=agg.losses,
                    goals_for=agg.goals_for if agg.played() > 0 else 0,
                    goals_against=agg.goals_against if agg.played() > 0 else 0,
                    points=agg.points(),
                    recent_form=agg.recent_form(),
                )
            )

        # Sorting (points desc, diff desc, goals_for desc, name asc)
        def sort_key(e: DivisionStandingEntry):
            diff = (
                (e.goals_for - e.goals_against)
                if (e.goals_for is not None and e.goals_against is not None)
                else 0
            )
            return (-e.points, -diff, -(e.goals_for or 0), e.team_name.lower())

        entries.sort(key=sort_key)
        # Assign positions sequentially
        for idx, e in enumerate(entries, start=1):
            e.position = idx  # dataclass not frozen; safe in GUI layer model

        return entries
