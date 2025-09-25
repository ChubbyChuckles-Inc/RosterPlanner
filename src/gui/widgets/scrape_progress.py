from __future__ import annotations

from dataclasses import dataclass
from typing import Optional
from PyQt6.QtWidgets import QWidget, QVBoxLayout, QLabel, QProgressBar, QFrame
from PyQt6.QtCore import Qt, pyqtSignal

__all__ = ["ScrapeProgressWidget", "ScrapePhase"]


@dataclass(frozen=True)
class ScrapePhase:
    key: str
    title: str
    weight: int  # relative weight toward overall progress


PHASES: list[ScrapePhase] = [
    ScrapePhase("landing", "Landing Page", 5),
    ScrapePhase("ranking_tables", "Ranking Tables", 15),
    ScrapePhase("division_rosters", "Division Rosters", 25),
    ScrapePhase("club_overviews", "Club Overviews", 10),
    ScrapePhase("club_team_pages", "Club Team Pages", 10),
    ScrapePhase("player_histories", "Player History Pages", 25),
    ScrapePhase("tracking_state", "Tracking State", 10),
]
_total_weight = sum(p.weight for p in PHASES)
_phase_index = {p.key: i for i, p in enumerate(PHASES)}


class ScrapeProgressWidget(QFrame):
    cancelled = pyqtSignal()

    def __init__(self, parent: Optional[QWidget] = None):
        super().__init__(parent)
        self.setObjectName("scrapeProgressWidget")
        self.setFrameShape(QFrame.Shape.StyledPanel)
        self.setFrameShadow(QFrame.Shadow.Raised)
        lay = QVBoxLayout(self)
        lay.setContentsMargins(8, 8, 8, 8)
        lay.setSpacing(4)
        self.phase_label = QLabel("Idle")
        self.phase_label.setObjectName("scrapePhaseLabel")
        self.detail_label = QLabel("")
        self.detail_label.setObjectName("scrapeDetailLabel")
        self.bar_phase = QProgressBar()
        self.bar_phase.setRange(0, 100)
        self.bar_phase.setValue(0)
        self.bar_total = QProgressBar()
        self.bar_total.setRange(0, 100)
        self.bar_total.setValue(0)
        self.bar_total.setFormat("Overall %p%")
        self.bar_phase.setFormat("Phase %p%")
        lay.addWidget(self.phase_label)
        lay.addWidget(self.detail_label)
        lay.addWidget(self.bar_phase)
        lay.addWidget(self.bar_total)
        self._current_phase: Optional[ScrapePhase] = None
        self._current_phase_progress = 0
        self._completed_weights = 0

    def start(self):  # reset
        self._current_phase = None
        self._current_phase_progress = 0
        self._completed_weights = 0
        self.phase_label.setText("Starting scrape...")
        self.detail_label.setText("")
        self.bar_phase.setValue(0)
        self.bar_total.setValue(0)

    def begin_phase(self, key: str, detail: str = ""):
        phase = _phase_index.get(key)
        if phase is None:
            return
        p = PHASES[phase]
        if self._current_phase and self._current_phase.key != key:
            # mark previous as complete if not already
            self._completed_weights += self._current_phase.weight
        self._current_phase = p
        self._current_phase_progress = 0
        self.phase_label.setText(p.title)
        self.detail_label.setText(detail)
        self.bar_phase.setValue(0)
        self._update_total()

    def update_phase_progress(self, fraction: float, detail: str = ""):
        if not self._current_phase:
            return
        fraction = max(0.0, min(1.0, fraction))
        self._current_phase_progress = int(fraction * 100)
        self.bar_phase.setValue(self._current_phase_progress)
        if detail:
            self.detail_label.setText(detail)
        self._update_total()

    def complete_phase(self):
        if not self._current_phase:
            return
        self.bar_phase.setValue(100)
        self._completed_weights += self._current_phase.weight
        self._current_phase = None
        self._current_phase_progress = 0
        self._update_total()

    def _update_total(self):
        # Weighted total percent
        running = self._completed_weights
        if self._current_phase:
            running += self._current_phase.weight * (self.bar_phase.value() / 100.0)
        pct = int((running / _total_weight) * 100)
        self.bar_total.setValue(pct)

    def finish(self):
        # finalize to 100%
        self._completed_weights = _total_weight
        self.bar_total.setValue(100)
        self.phase_label.setText("Complete")
        self.bar_phase.setValue(100)
