"""Layout Reflow Coordinator (Milestone 5.10.68).

Provides debounced layout reflow batching during rapid window resize operations
(e.g. user drags corner). Instead of allowing each intermediate resize to
trigger expensive recalculations (layout passes, data-driven repaints), we
collect resize events and apply a single *commit* callback after a quiet period.

Design Goals
------------
* Debounce semantics: last-event-wins after ``debounce_ms`` of inactivity.
* Optional max wait: ensure a commit at least every ``max_interval_ms`` even
  if user continuously drags (prevents starvation) (future parameter; omitted
  for initial milestone to keep scope focused).
* Reduced motion awareness: no motion transforms here, but we expose hook for
  future smooth scaling via lightweight transform if enabled.
* Testability: pure Python timer logic separated from QWidget concerns.

Public API
----------
class LayoutReflowCoordinator(QObject):
    set_debounce_ms(ms) -> None
    watch(widget, callback) -> None  # callback executed after debounce
    pending_count() -> int
    force_commit() -> None

Current Simplification
----------------------
We scope to top-level window resize events. Each registered widget's callback
receives its current size (QSize) at commit time.

Tests assert:
* Multiple rapid resize events -> single callback invocation.
* Separate widgets maintain independent debounce timers (shared queue processed).
* force_commit triggers immediate callbacks for pending items.

Future Extensions
-----------------
* Add optional transform-based interim scale (simulate CSS scale).
* Integrate performance instrumentation (time spent in callbacks).
"""

from __future__ import annotations
from typing import Callable, Dict, Optional, Set
from dataclasses import dataclass
from PyQt6.QtCore import QObject, QEvent, QTimer, QSize
from PyQt6.QtWidgets import QWidget


@dataclass
class _Watched:
    widget: QWidget
    callback: Callable[[QSize], None]
    dirty: bool = False


class LayoutReflowCoordinator(QObject):
    """Debounce resize-induced reflow work for watched widgets."""

    def __init__(self, debounce_ms: int = 90):
        super().__init__()
        self._debounce_ms = max(10, min(debounce_ms, 1000))
        self._watched: Dict[int, _Watched] = {}
        self._dirty_ids: Set[int] = set()
        self._timer: Optional[QTimer] = None

    # Configuration -----------------------------------------------------
    def set_debounce_ms(self, ms: int) -> None:
        self._debounce_ms = max(10, min(ms, 2000))
        # Timer will pick up new interval on next schedule.

    # Registration ------------------------------------------------------
    def watch(self, widget: QWidget, callback: Callable[[QSize], None]) -> None:
        wid = id(widget)
        if wid not in self._watched:
            self._watched[wid] = _Watched(widget=widget, callback=callback)
            widget.installEventFilter(self)

    # Introspection -----------------------------------------------------
    def pending_count(self) -> int:
        return len(self._dirty_ids)

    # Control -----------------------------------------------------------
    def force_commit(self) -> None:
        if self._dirty_ids:
            self._flush()

    # Internal ----------------------------------------------------------
    def _schedule(self) -> None:
        if self._timer is None:
            self._timer = QTimer(self)
            self._timer.setSingleShot(True)
            self._timer.timeout.connect(self._on_timeout)  # type: ignore[attr-defined]
        self._timer.start(self._debounce_ms)

    def _on_timeout(self):  # pragma: no cover - timer deterministic via force_commit in tests
        self._flush()

    def _flush(self):
        dirty = list(self._dirty_ids)
        self._dirty_ids.clear()
        for wid in dirty:
            watched = self._watched.get(wid)
            if not watched:
                continue
            w = watched.widget
            if w is None or not w.isVisible():  # skip invisible; still cleared
                continue
            try:
                watched.callback(w.size())
            except Exception:  # pragma: no cover - defensive
                pass
        # timer ends; recreated on next schedule
        if self._timer:
            self._timer.stop()
            self._timer = None

    # Qt Event Filter ---------------------------------------------------
    def eventFilter(self, obj: QObject, event: QEvent) -> bool:  # noqa: D401
        try:
            if isinstance(obj, QWidget) and event.type() == QEvent.Type.Resize:
                wid = id(obj)
                if wid in self._watched:
                    self._dirty_ids.add(wid)
                    self._schedule()
        except Exception:  # pragma: no cover
            pass
        return super().eventFilter(obj, event)


__all__ = ["LayoutReflowCoordinator"]
