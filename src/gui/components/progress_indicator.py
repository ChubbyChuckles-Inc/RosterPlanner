"""Progress Indicator Widgets (Milestone 5.10.67).

Provides two lightweight progress indicators:
 - DeterminateProgress: set explicit progress (0..1) with optional label.
 - IndeterminateProgress: looping bar animation (reduced-motion aware).

Design Goals:
 - Token-driven sizing & colors (consumed via QSS using objectName / properties).
 - Reduced motion: disable indeterminate animation timer when global reduced motion enabled.
 - Testable: expose current value, active animation flag.

Usage::
    w = DeterminateProgress(); w.set_progress(0.42)
    spinner = IndeterminateProgress(); spinner.start(); spinner.stop()

Both widgets avoid heavy painting; they implement paintEvent for custom bar.
"""

from __future__ import annotations
from typing import Optional
from PyQt6.QtCore import Qt, QTimer, QRectF
from PyQt6.QtGui import QPainter, QColor
from PyQt6.QtWidgets import QWidget

try:  # unified reduced-motion import path
    from src.gui.design import reduced_motion as _rm  # type: ignore
except ImportError:  # pragma: no cover
    from gui.design import reduced_motion as _rm  # type: ignore

__all__ = ["DeterminateProgress", "IndeterminateProgress"]


class DeterminateProgress(QWidget):
    """Simple horizontal progress bar.

    Properties exposed for QSS theming:
     - objectName: determinateProgress
     - dynamic property 'state': one of 'empty', 'partial', 'complete'
    """

    def __init__(self, parent: Optional[QWidget] = None):
        super().__init__(parent)
        self.setObjectName("determinateProgress")
        self._value: float = 0.0
        self._bar_color = QColor(80, 140, 220)
        self._track_color = QColor(40, 40, 40, 80)
        self.setFixedHeight(10)
        self._update_state_property()

    def set_progress(self, value: float):
        self._value = max(0.0, min(1.0, float(value)))
        self._update_state_property()
        self.update()

    def progress(self) -> float:
        return self._value

    def _update_state_property(self):
        if self._value <= 0.0:
            self.setProperty("state", "empty")
        elif self._value >= 0.999:
            self.setProperty("state", "complete")
        else:
            self.setProperty("state", "partial")

    def paintEvent(self, event):  # type: ignore[override]
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing, False)
        rect = self.rect()
        p.fillRect(rect, self._track_color)
        if self._value > 0:
            w = int(rect.width() * self._value)
            if w > 0:
                p.fillRect(0, 0, w, rect.height(), self._bar_color)


class IndeterminateProgress(QWidget):
    """Looping animated bar segment.

    When reduced motion is active, animation is disabled and a static mid-bar
    segment is shown.
    """

    def __init__(self, parent: Optional[QWidget] = None, *, interval_ms: int = 64):
        super().__init__(parent)
        self.setObjectName("indeterminateProgress")
        self.setFixedHeight(10)
        self._interval = max(16, min(interval_ms, 500))
        self._timer: Optional[QTimer] = None
        self._phase: float = 0.0
        self._bar_color = QColor(80, 140, 220)
        self._track_color = QColor(40, 40, 40, 80)
        self._active = False

    # Control -----------------------------------------------------------
    def start(self):
        if _rm.is_reduced_motion():
            self._active = False
            self.update()
            return
        self.show()
        if self._timer is None:
            self._timer = QTimer(self)
            self._timer.timeout.connect(self._on_tick)  # type: ignore[attr-defined]
            self._timer.start(self._interval)
        self._active = True
        # Immediate phase advance for deterministic test observation without relying purely on event loop timing
        self._phase = (self._phase + 0.02) % 1.0
        try:
            from PyQt6.QtCore import QTimer as _QT

            _QT.singleShot(self._interval // 2 or 1, self._on_tick)
        except Exception:  # pragma: no cover
            pass
        self.update()

    def stop(self):
        self._active = False
        if self._timer:
            try:
                self._timer.stop()
            except Exception:  # pragma: no cover
                pass
            self._timer = None
        self.update()

    def is_active(self) -> bool:
        return self._active

    # Animation ---------------------------------------------------------
    def _on_tick(self):  # pragma: no cover - timer driven
        if _rm.is_reduced_motion():
            self.stop()
            return
        self._phase = (self._phase + 0.02) % 1.0
        self.update()

    # Paint -------------------------------------------------------------
    def paintEvent(self, event):  # type: ignore[override]
        p = QPainter(self)
        rect = self.rect()
        p.fillRect(rect, self._track_color)
        # Segment geometry: move a bar across then wrap
        if _rm.is_reduced_motion():
            # Static centered segment
            seg_w = max(8, rect.width() // 5)
            x = (rect.width() - seg_w) // 2
        else:
            seg_w = max(8, rect.width() // 6)
            x = int((rect.width() + seg_w) * self._phase) - seg_w
            # Wrap-around blending (simple: clamp)
            if x + seg_w > rect.width():
                x = rect.width() - seg_w
            if x < 0:
                x = 0
        p.fillRect(QRectF(x, 0, seg_w, rect.height()), self._bar_color)

    # Convenience for tests ---------------------------------------------
    def debug_phase(self) -> float:
        return self._phase
