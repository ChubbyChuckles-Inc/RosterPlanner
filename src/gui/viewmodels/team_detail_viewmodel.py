"""ViewModel for Team Detail View (Milestone 5.1).

Separates data/derivation logic from the Qt widget so that unit tests
can exercise behavior without needing a QApplication.
"""

from __future__ import annotations
from dataclasses import dataclass, field
from typing import List, Optional

from gui.models import TeamRosterBundle, PlayerEntry, MatchDate


@dataclass
class TeamSummary:
    player_count: int = 0
    live_pz_count: int = 0
    avg_live_pz: Optional[float] = None

    def as_text(self) -> str:
        if self.player_count == 0:
            return "No players"
        if self.live_pz_count == 0:
            return f"{self.player_count} players (no LivePZ data)"
        return f"{self.player_count} players | LivePZ entries: {self.live_pz_count} | Avg: {self.avg_live_pz:.1f}"


class TeamDetailViewModel:
    """Holds current team roster bundle and exposes derived summary.

    Methods avoid any PyQt dependencies to stay pure-python for tests.
    """

    def __init__(self):
        self._bundle: Optional[TeamRosterBundle] = None
        self.summary: TeamSummary = TeamSummary()

    # ------------------------------------------------------------------
    def set_bundle(self, bundle: TeamRosterBundle):
        self._bundle = bundle
        self._recompute_summary()

    def bundle(self) -> Optional[TeamRosterBundle]:  # pragma: no cover - trivial accessor
        return self._bundle

    def players(self) -> List[PlayerEntry]:
        return list(self._bundle.players) if self._bundle else []

    def matches(self) -> List[MatchDate]:
        return list(self._bundle.match_dates) if self._bundle else []

    # ------------------------------------------------------------------
    def _recompute_summary(self):
        if not self._bundle or not self._bundle.players:
            self.summary = TeamSummary()
            return
        players = self._bundle.players
        values = [p.live_pz for p in players if p.live_pz is not None]
        avg = sum(values) / len(values) if values else None
        self.summary = TeamSummary(
            player_count=len(players), live_pz_count=len(values), avg_live_pz=avg
        )


__all__ = ["TeamDetailViewModel", "TeamSummary"]
