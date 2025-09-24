"""Layout Shift Monitor Service (Milestone 5.10.64).

Collects a cumulative "layout shift" metric inspired by web CLS concepts to
surface unexpected widget geometry movement after initial layout. This helps
identify jittery UI updates (e.g., late-arriving data changing sizes).

Design Goals
------------
* Lightweight: single eventFilter for registered widgets.
* Deterministic scoring: approximate shift magnitude using delta position
  plus scaled delta size.
* Safe: failures are swallowed (instrumentation must not crash UI).
* Testable: pure Python with explicit APIs (no global singletons required).

Scoring Heuristic
-----------------
For a geometry change from (x,y,w,h) -> (x',y',w',h'):
  dx = |x'-x|, dy = |y'-y|, dw = |w'-w|, dh = |h'-h|
  score = dx + dy + 0.25*(dw + dh)

This biases pure movement (positional jitter) higher than minor size growth.

Public API
----------
class LayoutShiftMonitor:
    register(widget) -> None
    cumulative_score() -> float
    records -> list[LayoutShiftRecord]
    reset() -> None

Edge Cases
----------
* First geometry seen per widget is baseline (no score).
* Resize/move events during an optional "warm-up" window (ms) can be skipped
  (future enhancement). For now everything after registration counts.
* Tiny movements (<= ignore_threshold) ignored to reduce noise.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, List, Optional

from PyQt6.QtCore import QObject, QEvent, QRect
from PyQt6.QtWidgets import QWidget

__all__ = [
    "LayoutShiftRecord",
    "LayoutShiftMonitor",
]


@dataclass(frozen=True)
class LayoutShiftRecord:
    widget_name: str
    old_rect: QRect
    new_rect: QRect
    score: float


class LayoutShiftMonitor(QObject):
    """Monitor geometry changes for registered widgets.

    Attach via ``register(widget)``. Uses an event filter to observe move and
    resize events without subclassing application widgets.
    """

    def __init__(self, ignore_threshold: int = 1):  # pixel threshold
        super().__init__()
        self._ignore_threshold = max(0, ignore_threshold)
        self._last_geometry: Dict[int, QRect] = {}
        self._records: List[LayoutShiftRecord] = []
        self._cumulative: float = 0.0

    # Public -----------------------------------------------------------------
    def register(self, widget: QWidget) -> None:
        try:
            wid = id(widget)
            if wid not in self._last_geometry:
                self._last_geometry[wid] = QRect(widget.geometry())
                widget.installEventFilter(self)
        except Exception:  # pragma: no cover - defensive
            pass

    def cumulative_score(self) -> float:
        return self._cumulative

    @property
    def records(self) -> List[LayoutShiftRecord]:  # pragma: no cover - trivial
        return list(self._records)

    def reset(self) -> None:
        self._records.clear()
        self._cumulative = 0.0
        # Keep baselines to continue accumulation without re-register.

    # Internal ----------------------------------------------------------------
    def _compute_score(self, old: QRect, new: QRect) -> float:
        dx = abs(new.x() - old.x())
        dy = abs(new.y() - old.y())
        dw = abs(new.width() - old.width())
        dh = abs(new.height() - old.height())
        if (
            dx <= self._ignore_threshold
            and dy <= self._ignore_threshold
            and dw <= self._ignore_threshold
            and dh <= self._ignore_threshold
        ):
            return 0.0
        return dx + dy + 0.25 * (dw + dh)

    # Qt Event Filter ---------------------------------------------------------
    def eventFilter(self, obj: QObject, event: QEvent) -> bool:  # noqa: D401
        try:
            if isinstance(obj, QWidget) and event.type() in (QEvent.Type.Resize, QEvent.Type.Move):
                wid = id(obj)
                old: Optional[QRect] = self._last_geometry.get(wid)
                new_rect = QRect(obj.geometry())
                if old is not None:
                    score = self._compute_score(old, new_rect)
                    if score > 0:
                        rec = LayoutShiftRecord(
                            widget_name=obj.objectName() or f"widget-{wid}",
                            old_rect=old,
                            new_rect=new_rect,
                            score=score,
                        )
                        self._records.append(rec)
                        self._cumulative += score
                self._last_geometry[wid] = new_rect
        except Exception:  # pragma: no cover - defensive path
            pass
        return super().eventFilter(obj, event)
