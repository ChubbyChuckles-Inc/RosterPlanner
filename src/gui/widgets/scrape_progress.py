from __future__ import annotations

from dataclasses import dataclass
from typing import Optional, Dict, Deque, List
from collections import deque
import json
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
from PyQt6.QtCore import (
    Qt,
    pyqtSignal,
    QElapsedTimer,
    QPropertyAnimation,
    QEasingCurve,
    QTimer,
)
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
    pause_requested = pyqtSignal(bool)  # True=pause, False=resume
    copy_summary_requested = pyqtSignal(str)
    error_count_changed = pyqtSignal(int)
    queue_count_changed = pyqtSignal(int)

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
        self.bar_phase.setObjectName("phaseBar")
        self.bar_total = QProgressBar()
        self.bar_total.setRange(0, 100)
        self.bar_total.setValue(0)
        self.bar_total.setObjectName("totalBar")
        self.bar_total.setFormat("Overall %p%")
        self.bar_phase.setFormat("Phase %p%")
        header = QHBoxLayout()
        header.setContentsMargins(0, 0, 0, 0)
        header.setSpacing(6)
        header.addWidget(self.phase_label, 1)
        self.eta_label = QLabel("ETA --:--")
        self.eta_label.setObjectName("scrapeEtaLabel")
        header.addWidget(self.eta_label)
        self.btn_pause = QPushButton("Pause")
        self.btn_pause.clicked.connect(self._on_pause_clicked)  # type: ignore
        header.addWidget(self.btn_pause)
        self.btn_cancel = QPushButton("Cancel")
        self.btn_cancel.clicked.connect(self._on_cancel_clicked)  # type: ignore
        header.addWidget(self.btn_cancel)
        lay.addLayout(header)
        # Detail panel
        self._detail_frame = QFrame()
        df_lay = QVBoxLayout(self._detail_frame)
        df_lay.setContentsMargins(4, 4, 4, 4)
        df_lay.setSpacing(2)
        self.detail_counts_label = QLabel("Teams: 0 | Players: 0 | Matches: 0")
        self.detail_counts_label.setObjectName("scrapeCountsLabel")
        self.net_label = QLabel("Net: -- ms")
        self.net_label.setObjectName("scrapeNetLabel")
        self.error_badge = QLabel("")
        self.error_badge.setObjectName("scrapeErrorBadge")
        self.error_badge.setVisible(False)
        self.queue_badge = QLabel("")
        self.queue_badge.setObjectName("scrapeQueueBadge")
        self.queue_badge.setVisible(False)
        df_lay.addWidget(self.detail_counts_label)
        df_lay.addWidget(self.net_label)
        df_lay.addWidget(self.error_badge)
        df_lay.addWidget(self.queue_badge)
        lay.addWidget(self._detail_frame)
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
        # Dedicated opacity effect for phase label animation (avoid recreating during animation)
        from PyQt6.QtWidgets import QGraphicsOpacityEffect as _QOE

        self._phase_opacity_effect = _QOE(self.phase_label)
        self.phase_label.setGraphicsEffect(self._phase_opacity_effect)
        self._phase_label_anim: QPropertyAnimation | None = None
        # History & diagnostics state
        self._history_path = os.path.join(
            os.getenv("ROSTERPLANNER_DATA_DIR", "data"), "scrape_history.json"
        )
        self._history: Deque[float] = deque(maxlen=20)
        self._load_history()
        self._phase_started_ms: Dict[str, int] = {}
        self._paused = False
        self._errors: List[str] = []
        self._net_latency: Dict[str, float] = {}
        self._queued_jobs = 0
        # ETA helpers
        self._eta_window: Deque[float] = deque(maxlen=8)
        # Accessibility labels
        self.phase_label.setAccessibleName("Current Phase")
        self.detail_label.setAccessibleName("Phase Detail")
        self.bar_phase.setAccessibleName("Phase Progress")
        self.bar_total.setAccessibleName("Overall Progress")
        self.error_badge.setAccessibleName("Errors Badge")
        self.queue_badge.setAccessibleName("Queue Badge")
        self.eta_label.setAccessibleName("Estimated Time Remaining")

    # ---- Public update hooks (called by MainWindow) -----------------------
    def update_counts(self, teams: int, players: int, matches: int):  # pragma: no cover
        self.detail_counts_label.setText(
            f"Teams: {teams} | Players: {players} | Matches: {matches}"
        )

    def update_net_latency(self, phase: str, total_latency: float):  # pragma: no cover
        self._net_latency[phase] = total_latency
        agg_ms = int(sum(self._net_latency.values()) * 1000)
        self.net_label.setText(f"Net: {agg_ms} ms")

    def append_error(self, phase: str, message: str):  # pragma: no cover
        self._errors.append(f"[{phase}] {message}")
        self._update_error_badge()

    def update_queue(self, count: int):  # pragma: no cover
        self._queued_jobs = count
        self._update_queue_badge()
        self.queue_count_changed.emit(count)

    def start(self):  # reset
        self._current_phase = None
        self._current_phase_progress = 0
        self._completed_weights = 0
        self.phase_label.setText("Starting scrape...")
        self.detail_label.setText("")
        self.bar_phase.setValue(0)
        self.bar_total.setValue(0)
        self.btn_cancel.setEnabled(True)
        self.btn_pause.setEnabled(True)
        self.btn_pause.setText("Pause")
        self._debounce_timer.restart()
        # Force first progress update immediately (set last update negative)
        self._last_update_ms = -10_000
        # Reset phase statuses
        for p in PHASES:
            self._phase_status[p.key] = "pending"
        self._refresh_phase_styles()
        self._phase_started_ms.clear()
        self._errors.clear()
        self._net_latency.clear()
        self._queued_jobs = 0
        self._update_error_badge()

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
        self._phase_started_ms[key] = self._debounce_timer.elapsed()
        self._update_total()
        self._animate_phase_label()
        self._update_eta_label()

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
        self._update_eta_label()

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
        # Recompute ETA using progress so far (do NOT treat each phase as final run)
        self._update_eta_label()

    def _update_total(self):
        # Weighted total percent
        running = self._completed_weights
        if self._current_phase:
            running += self._current_phase.weight * (self.bar_phase.value() / 100.0)
        pct = int((running / _total_weight) * 100)
        self.bar_total.setValue(pct)

    def finish(self):
        # finalize to 100%
        # Stop any running phase label animation to prevent painter errors during fade-out
        try:
            if (
                self._phase_label_anim
                and self._phase_label_anim.state() != QPropertyAnimation.State.Stopped
            ):
                self._phase_label_anim.stop()
        except Exception:
            pass
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
        # Append total run duration to history for future ETA predictions
        try:
            total_duration_s = self._debounce_timer.elapsed() / 1000.0
            if total_duration_s > 0.5:  # ignore trivially short runs
                self._history.append(total_duration_s)
        except Exception:
            pass
        self._save_history()
        # Mark ETA final now
        self._update_eta_label(final=True)
        # Emit summary JSON for copy convenience
        summary = self._build_summary_json()
        self.copy_summary_requested.emit(summary)
        self._schedule_close()

    # ---- Internal helpers -------------------------------------------------
    def _load_history(self):  # pragma: no cover
        try:
            if os.path.exists(self._history_path):
                with open(self._history_path, "r", encoding="utf-8") as f:
                    data = json.load(f)
                for v in data.get("durations", [])[-20:]:
                    try:
                        self._history.append(float(v))
                    except Exception:
                        pass
        except Exception:
            pass

    def _save_history(self):  # pragma: no cover
        try:
            os.makedirs(os.path.dirname(self._history_path), exist_ok=True)
            with open(self._history_path, "w", encoding="utf-8") as f:
                json.dump({"durations": list(self._history)}, f)
        except Exception:
            pass

    def _update_error_badge(self):  # pragma: no cover
        total_err = len(self._errors)
        parts = []
        if total_err:
            parts.append(f"Errors: {total_err}")
        # queue now separate badge
        if parts:
            self.error_badge.setText(" | ".join(parts))
            self.error_badge.setVisible(True)
        else:
            self.error_badge.setVisible(False)
        self.error_count_changed.emit(total_err)

    def _update_queue_badge(self):  # pragma: no cover
        if self._queued_jobs:
            self.queue_badge.setText(f"Queued: {self._queued_jobs}")
            self.queue_badge.setVisible(True)
        else:
            self.queue_badge.setVisible(False)

    def _on_pause_clicked(self):  # pragma: no cover
        self._paused = not self._paused
        self.btn_pause.setText("Resume" if self._paused else "Pause")
        self.pause_requested.emit(self._paused)

    def _build_summary_json(self) -> str:
        summary = {
            "phases": [p.key for p in PHASES],
            "errors": self._errors,
            "net_latency_ms": {k: int(v * 1000) for k, v in self._net_latency.items()},
            "history_count": len(self._history),
            "queued_jobs": self._queued_jobs,
        }
        try:
            return json.dumps(summary, indent=2)
        except Exception:
            return "{}"

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
        # Base stylesheet with token placeholders; replaced in _apply_theme_colors.
        base_qss = """
#scrapeProgressWidget { background: rgba(30,38,50,0.90); border:1px solid #364250; border-radius:10px; }
#scrapeProgressWidget QLabel#scrapePhaseLabel { font-size:15px; font-weight:600; color:__FG_PRIMARY__; }
#scrapeProgressWidget QLabel#scrapeEtaLabel { font-size:11px; color:__FG_SUBTLE__; padding-left:6px; }
#scrapeProgressWidget QLabel#scrapeDetailLabel { font-size:11px; color:__FG_SUBTLE__; }
#scrapeProgressWidget QProgressBar { height:18px; border:1px solid __BORDER__; border-radius:9px; background:__BAR_BG__; text-align:center; font-size:11px; color:__BAR_TEXT__; }
#scrapeProgressWidget QProgressBar#phaseBar::chunk { border-radius:9px; background: qlineargradient(x1:0,y1:0,x2:1,y2:0, stop:0 __ACCENT_START__, stop:1 __ACCENT_END__); }
#scrapeProgressWidget QProgressBar#totalBar::chunk { border-radius:9px; background: qlineargradient(x1:0,y1:0,x2:1,y2:0, stop:0 __ACCENT_ALT_START__, stop:1 __ACCENT_ALT_END__); }
#scrapeProgressWidget QPushButton { background:__BTN_BG__; color:__FG_PRIMARY__; border:1px solid __BORDER__; padding:4px 10px; border-radius:6px; }
#scrapeProgressWidget QPushButton:hover:enabled { background:__BTN_BG_HOVER__; }
#scrapeProgressWidget QPushButton:disabled { background:__BTN_BG_DISABLED__; color:__FG_DISABLED__; }
#scrapeProgressWidget QFrame#phaseRow { background:transparent; }
#scrapeProgressWidget QLabel[phaseState="pending"] { color:__PHASE_PENDING__; font-size:11px; }
#scrapeProgressWidget QLabel[phaseState="active"] { color:__PHASE_ACTIVE__; font-weight:600; }
#scrapeProgressWidget QLabel[phaseState="done"] { color:__PHASE_DONE__; font-weight:500; }
#scrapeProgressWidget QLabel#scrapeErrorBadge { background:#7a3d2f; color:#ffddcc; padding:2px 6px; border-radius:8px; font-size:10px; }
#scrapeProgressWidget QLabel#scrapeQueueBadge { background:#2f517a; color:#d6e9ff; padding:2px 6px; border-radius:8px; font-size:10px; }
#scrapeProgressWidget QLabel#scrapeNetLabel { font-size:10px; color:__FG_SUBTLE__; }
#scrapeProgressWidget QLabel#scrapeCountsLabel { font-size:10px; color:__FG_SUBTLE__; }
"""
        self._base_qss_template = base_qss
        self._apply_theme_colors()

    def _apply_theme_colors(self):  # pragma: no cover
        # Try to pull dynamic colors from theme service; otherwise fallback palette.
        try:
            from gui.services.service_locator import services as _services  # type: ignore

            theme_svc = _services.try_get("theme_service") if _services else None
            colors = theme_svc.colors() if (theme_svc and hasattr(theme_svc, "colors")) else {}
        except Exception:
            colors = {}
        # Fallbacks
        accent = colors.get("accent.base", "#3D8BFD")
        accent_end = colors.get("accent.alt", "#6F4BFF")
        accent_alt = colors.get("accent.soft", "#34c3ff")
        accent_alt_end = colors.get("accent.softAlt", "#66e1ff")
        fg_primary = colors.get("text.primary", "#E8F1FF")
        fg_subtle = colors.get("text.secondary", "#9db2c6")
        fg_disabled = colors.get("text.disabled", "#55616e")
        bar_bg = colors.get("surface.sunken", "#11161c")
        btn_bg = colors.get("surface.button", "#2e3a48")
        btn_bg_hover = colors.get("surface.button.hover", "#3a4858")
        btn_bg_disabled = colors.get("surface.button.disabled", "#1f272f")
        border = colors.get("border.medium", "#415064")
        phase_pending = colors.get("text.muted", "#6d7a8a")
        phase_active = fg_primary
        phase_done = colors.get("success", "#48c78e")

        # Ensure sufficient contrast for bar text by picking white or near-black
        def _contrasting(c: str) -> str:
            c = c.lstrip("#")
            if len(c) == 3:
                c = "".join(ch * 2 for ch in c)
            try:
                r, g, b = int(c[0:2], 16), int(c[2:4], 16), int(c[4:6], 16)
                luma = 0.2126 * r + 0.7152 * g + 0.0722 * b
                return "#000000" if luma > 180 else "#FFFFFF"
            except Exception:
                return "#FFFFFF"

        bar_text = _contrasting(accent)

        qss = self._base_qss_template
        repl = {
            "__ACCENT_START__": accent,
            "__ACCENT_END__": accent_end,
            "__ACCENT_ALT_START__": accent_alt,
            "__ACCENT_ALT_END__": accent_alt_end,
            "__FG_PRIMARY__": fg_primary,
            "__FG_SUBTLE__": fg_subtle,
            "__FG_DISABLED__": fg_disabled,
            "__BAR_BG__": bar_bg,
            "__BAR_TEXT__": bar_text,
            "__BTN_BG__": btn_bg,
            "__BTN_BG_HOVER__": btn_bg_hover,
            "__BTN_BG_DISABLED__": btn_bg_disabled,
            "__BORDER__": border,
            "__PHASE_PENDING__": phase_pending,
            "__PHASE_ACTIVE__": phase_active,
            "__PHASE_DONE__": phase_done,
        }
        for k, v in repl.items():
            qss = qss.replace(k, v)
        self.setStyleSheet(qss)

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

    # ---- ETA + animation helpers -----------------------------------------
    def _update_eta_label(self, final: bool = False):  # pragma: no cover
        try:
            elapsed_s = self._debounce_timer.elapsed() / 1000.0
        except Exception:
            elapsed_s = 0.0

        overall_frac = self.bar_total.value() / 100.0

        if final:
            # Final run complete: show Done
            self.eta_label.setText("Done")
            return

        if overall_frac <= 0.01:
            self.eta_label.setText("ETA --:--")
            return

        # Seed estimation window if empty
        if not self._eta_window:
            if self._history:
                avg = sum(self._history) / len(self._history)
                if avg > 0:
                    self._eta_window.append(avg)
            else:
                # First-ever run: derive naive projection from current pace once enough progress
                if overall_frac > 0.03 and elapsed_s > 1.0:
                    projected_total = elapsed_s / max(overall_frac, 1e-3)
                    self._eta_window.append(projected_total)
                else:
                    self.eta_label.setText("ETA --:--")
                    return

        if not self._eta_window:  # still empty
            self.eta_label.setText("ETA --:--")
            return

        avg_total = sum(self._eta_window) / len(self._eta_window)
        remaining_s = max(0.0, avg_total - elapsed_s)
        mins = int(remaining_s // 60)
        secs = int(remaining_s % 60)
        self.eta_label.setText(f"ETA {mins:02d}:{secs:02d}")

    def _animate_phase_label(self):  # pragma: no cover
        try:
            # Cancel previous animation if still running
            if (
                self._phase_label_anim
                and self._phase_label_anim.state() != QPropertyAnimation.State.Stopped
            ):
                self._phase_label_anim.stop()
            # Reset starting opacity
            self._phase_opacity_effect.setOpacity(0.35)
            anim = QPropertyAnimation(self._phase_opacity_effect, b"opacity", self)
            anim.setDuration(280)
            anim.setStartValue(0.35)
            anim.setEndValue(1.0)
            anim.setEasingCurve(QEasingCurve.Type.OutCubic)
            anim.start(QPropertyAnimation.DeletionPolicy.DeleteWhenStopped)
            self._phase_label_anim = anim
        except Exception:
            pass
