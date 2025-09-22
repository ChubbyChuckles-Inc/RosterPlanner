"""PlayerDetailViewModel (Milestone 5.2 initial scaffold).

Provides derived summary statistics for a player's historical
performance entries (placeholder dataset until real ingestion).
"""

from __future__ import annotations
from dataclasses import dataclass
from typing import List, Optional

from gui.models import PlayerHistoryEntry, PlayerEntry


@dataclass
class PlayerSummary:
    entries: int = 0
    total_delta: int = 0
    avg_delta: Optional[float] = None

    def as_text(self) -> str:
        if self.entries == 0:
            return "No history data"
        if self.avg_delta is None:
            return f"{self.entries} entries | delta: 0"
        return f"{self.entries} entries | total: {self.total_delta} | avg: {self.avg_delta:.1f}"


class PlayerDetailViewModel:
    def __init__(self, player: PlayerEntry):
        self.player = player
        self._history: List[PlayerHistoryEntry] = []
        self.summary = PlayerSummary()

    def set_history(self, history: List[PlayerHistoryEntry]):
        self._history = list(history)
        self._recompute()

    def history(self) -> List[PlayerHistoryEntry]:  # pragma: no cover - trivial
        return list(self._history)

    def _recompute(self):
        if not self._history:
            self.summary = PlayerSummary()
            return
        deltas = [h.live_pz_delta for h in self._history if h.live_pz_delta is not None]
        total = sum(deltas) if deltas else 0
        avg = (total / len(deltas)) if deltas else None
        self.summary = PlayerSummary(entries=len(self._history), total_delta=total, avg_delta=avg)


__all__ = ["PlayerDetailViewModel", "PlayerSummary"]
