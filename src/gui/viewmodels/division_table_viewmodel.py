"""ViewModel for Division Table View (Milestone 5.3).

Takes raw `DivisionStandingEntry` objects and uses `DivisionTableNormalizer`
to produce display-ready row data plus summary statistics.
"""

from __future__ import annotations
from dataclasses import dataclass
from typing import List, Optional

from gui.models import DivisionStandingEntry
from gui.services.division_table_normalizer import (
    DivisionTableNormalizer,
    NormalizedDivisionRow,
)

__all__ = ["DivisionTableViewModel", "DivisionSummary"]


@dataclass
class DivisionSummary:
    team_count: int = 0
    top_points: Optional[int] = None

    def as_text(self) -> str:
        if self.team_count == 0:
            return "No teams"
        if self.top_points is None:
            return f"{self.team_count} teams"
        return f"{self.team_count} teams | Top points: {self.top_points}"


class DivisionTableViewModel:
    def __init__(self, normalizer: DivisionTableNormalizer | None = None):
        self._normalizer = normalizer or DivisionTableNormalizer()
        self._raw: List[DivisionStandingEntry] = []
        self._rows: List[NormalizedDivisionRow] = []
        self.summary = DivisionSummary()

    def set_rows(self, rows: List[DivisionStandingEntry]):
        self._raw = list(rows)
        self._rows = self._normalizer.normalize(self._raw)
        self._recompute_summary()

    def rows(self) -> List[NormalizedDivisionRow]:  # pragma: no cover - trivial
        return list(self._rows)

    def _recompute_summary(self):
        if not self._raw:
            self.summary = DivisionSummary()
            return
        top_points = max(r.points for r in self._raw) if self._raw else None
        self.summary = DivisionSummary(team_count=len(self._raw), top_points=top_points)
