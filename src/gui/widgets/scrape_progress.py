from __future__ import annotations

from dataclasses import dataclass
from typing import Optional, Dict
import os
from PyQt6.QtWidgets import (
    QWidget,
    QVBoxLayout,
    QLabel,
    QProgressBar,
    QFrame,
    QPushButton,
    QHBoxLayout,
)
from PyQt6.QtCore import Qt, pyqtSignal, QElapsedTimer, QPropertyAnimation, QEasingCurve, QTimer
from PyQt6.QtWidgets import QGraphicsOpacityEffect

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
    closed = pyqtSignal()

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
        header = QHBoxLayout()
        header.setContentsMargins(0, 0, 0, 0)
        header.setSpacing(6)
        header.addWidget(self.phase_label, 1)
        self.btn_cancel = QPushButton("Cancel")
        self.btn_cancel.clicked.connect(self._on_cancel_clicked)  # type: ignore
        header.addWidget(self.btn_cancel)
        lay.addLayout(header)
        # Phase list container
        self._phase_rows_container = QVBoxLayout()
        self._phase_rows_container.setContentsMargins(0, 0, 0, 0)
        self._phase_rows_container.setSpacing(2)
        lay.addLayout(self._phase_rows_container)
        lay.addWidget(self.detail_label)
        lay.addWidget(self.bar_phase)
        lay.addWidget(self.bar_total)
        self._current_phase: Optional[ScrapePhase] = None
        self._current_phase_progress = 0
        self._completed_weights = 0
        self._debounce_timer = QElapsedTimer()
        self._debounce_timer.start()
        self._last_update_ms = 0
        self._debounce_interval_ms = 120  # ms between progress UI updates (except completion)
        self._phase_labels: Dict[str, QLabel] = {}
        self._phase_status: Dict[str, str] = {}
        self._build_phase_rows()
        self._install_styles()
        # Opacity effect for fade-out
        self._fx = QGraphicsOpacityEffect(self)
        self.setGraphicsEffect(self._fx)
        self._fx.setOpacity(1.0)

    def start(self):  # reset
        self._current_phase = None
        self._current_phase_progress = 0
        self._completed_weights = 0
        self.phase_label.setText("Starting scrape...")
        self.detail_label.setText("")
        self.bar_phase.setValue(0)
        self.bar_total.setValue(0)
        self.btn_cancel.setEnabled(True)
        self._debounce_timer.restart()
        # Force first progress update immediately (set last update negative)
        self._last_update_ms = -10_000
        # Reset phase statuses
        for p in PHASES:
            self._phase_status[p.key] = "pending"
        self._refresh_phase_styles()

    def begin_phase(self, key: str, detail: str = ""):
        phase = _phase_index.get(key)
        if phase is None:
            return
        p = PHASES[phase]
        # Do not auto-complete previous phase here; caller must invoke complete_phase()
        self._current_phase = p
        self._current_phase_progress = 0
        self.phase_label.setText(p.title)
        self.detail_label.setText(detail)
        self.bar_phase.setValue(0)
        # Allow immediate first progress update for new phase
        self._last_update_ms = -10_000
        # Update phase marker statuses
        for k, status in list(self._phase_status.items()):
            if status == "active" and k != key:
                # Active phase switched without completion: mark as pending again (edge case)
                self._phase_status[k] = "pending"
        self._phase_status[key] = "active"
        self._refresh_phase_styles()
        self._update_total()

    def update_phase_progress(self, fraction: float, detail: str = ""):
        if not self._current_phase:
            return
        now = self._debounce_timer.elapsed()
        fraction = max(0.0, min(1.0, fraction))
        # Allow immediate if completion or enough time passed
        if fraction < 1.0 and (now - self._last_update_ms) < self._debounce_interval_ms:
            return
        self._last_update_ms = now
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
        # Mark status done
        if self._current_phase.key in self._phase_status:
            self._phase_status[self._current_phase.key] = "done"
        self._refresh_phase_styles()
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
        self.btn_cancel.setEnabled(False)
        # Mark any active phase done
        if self._current_phase:
            self._phase_status[self._current_phase.key] = "done"
            self._current_phase = None
        self._refresh_phase_styles()
        self._schedule_close()

    def _on_cancel_clicked(self):  # pragma: no cover
        self.btn_cancel.setEnabled(False)
        self.phase_label.setText("Cancelling...")
        self.cancelled.emit()
        # Show cancelling status and then fade out
        self._schedule_close(cancelled=True)

    # ---- Phase list helpers -------------------------------------------------
    def _build_phase_rows(self):
        # Clear existing
        while self._phase_rows_container.count():
            item = self._phase_rows_container.takeAt(0)
            w = item.widget()
            if w:
                w.deleteLater()
        self._phase_labels.clear()
        self._phase_status.clear()
        for p in PHASES:
            row = QHBoxLayout()
            row.setContentsMargins(0, 0, 0, 0)
            row.setSpacing(4)
            bullet = QLabel("●")
            bullet.setObjectName(f"phaseBullet_{p.key}")
            lbl = QLabel(p.title)
            lbl.setObjectName(f"phaseLabel_{p.key}")
            lbl.setProperty("phaseKey", p.key)
            row.addWidget(bullet)
            row.addWidget(lbl, 1)
            wrapper = QFrame()
            wrapper.setObjectName("phaseRow")
            wrapper.setLayout(row)
            self._phase_rows_container.addWidget(wrapper)
            self._phase_labels[p.key] = lbl
            self._phase_status[p.key] = "pending"
        spacer = QWidget()
        spacer.setFixedHeight(4)
        self._phase_rows_container.addWidget(spacer)
        self._refresh_phase_styles()

    def _refresh_phase_styles(self):
        for p in PHASES:
            lbl = self._phase_labels.get(p.key)
            if not lbl:
                continue
            status = self._phase_status.get(p.key, "pending")
            base = "phaseItem"
            if status == "active":
                cls = base + "Active"
            elif status == "done":
                cls = base + "Done"
            else:
                cls = base + "Pending"
            lbl.setProperty("phaseState", status)
            # Force style refresh
            lbl.style().unpolish(lbl)
            lbl.style().polish(lbl)

    def _install_styles(self):
        # Local modern styling (scoped by parent object names)
        self.setStyleSheet(
            """
#scrapeProgressWidget { background: rgba(30,38,50,0.85); border:1px solid #3a4658; border-radius:10px; }
#scrapeProgressWidget QLabel#scrapePhaseLabel { font-size:15px; font-weight:600; color:#E8F1FF; }
#scrapeProgressWidget QLabel#scrapeDetailLabel { font-size:11px; color:#B8C4D2; }
#scrapeProgressWidget QProgressBar { height:16px; border:1px solid #2d3642; border-radius:8px; background:#1e2530; text-align:center; font-size:10px; }
#scrapeProgressWidget QProgressBar::chunk { border-radius:8px; background: qlineargradient(x1:0,y1:0,x2:1,y2:0, stop:0 #3D8BFD, stop:1 #6F4BFF); }
#scrapeProgressWidget QPushButton { background:#2e3a48; color:#E8F1FF; border:1px solid #415064; padding:4px 10px; border-radius:6px; }
#scrapeProgressWidget QPushButton:hover:enabled { background:#384758; }
#scrapeProgressWidget QPushButton:disabled { background:#1f272f; color:#55616e; }
#scrapeProgressWidget QFrame#phaseRow { background:transparent; }
#scrapeProgressWidget QLabel[phaseState="pending"] { color:#6d7a8a; font-size:11px; }
#scrapeProgressWidget QLabel[phaseState="active"] { color:#FFFFFF; font-weight:600; }
#scrapeProgressWidget QLabel[phaseState="done"] { color:#48c78e; font-weight:500; }
"""
        )

    # ---- Fade / Close -------------------------------------------------------
    def _schedule_close(self, cancelled: bool = False):
        # In test mode avoid animations for predictability
        if os.getenv("RP_TEST_MODE") == "1":
            QTimer.singleShot(10, self._emit_closed)
            return
        # Delay slightly to let user see 100% or cancelling state
        delay = 600 if not cancelled else 300
        QTimer.singleShot(delay, self._start_fade)

    def _start_fade(self):
        anim = QPropertyAnimation(self._fx, b"opacity", self)
        anim.setDuration(550)
        anim.setStartValue(1.0)
        anim.setEndValue(0.0)
        anim.setEasingCurve(QEasingCurve.Type.InOutCubic)
        anim.finished.connect(self._emit_closed)  # type: ignore
        anim.start(QPropertyAnimation.DeletionPolicy.DeleteWhenStopped)

    def _emit_closed(self):  # pragma: no cover - simple signal
        self.closed.emit()
