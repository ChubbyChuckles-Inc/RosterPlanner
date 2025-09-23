"""DPI / device pixel ratio change detection service (Milestone 5.10.56).

Responsibilities:
 - Query current primary screen logical DPI / devicePixelRatio.
 - Expose a normalized scaling factor relative to a 96 DPI baseline.
 - Install a Qt event filter to listen for screen changes (QEvent.ScreenChangeInternal)
   and QGuiApplication::primaryScreenChanged signals.
 - Debounce rapid successive changes (e.g., when moving between monitors).
 - Publish GUIEvent.DPI_SCALE_CHANGED via EventBus when factor changes more than a threshold (1%).

Rationale:
 Multi‑monitor environments (Windows esp.) can have heterogeneous DPI. The design token
 scaling (typography, spacing) can respond to this to keep physical sizing consistent.
 For now we simply expose the factor; consumers (e.g., DensityService, ThemeService) may
 subscribe in future to recompute derived metrics.

Testing strategy:
 - Unit test will fake a sequence of scale factors by monkeypatching the provider method.
 - We assert publish occurs only when threshold exceeded.

Note: Direct screen DPI querying requires a QApplication; tests create a minimal instance.
"""

from __future__ import annotations
from dataclasses import dataclass
from typing import Callable, Optional
from PyQt6.QtCore import QObject, QEvent, QTimer
from PyQt6.QtGui import QGuiApplication

from .service_locator import services
from .event_bus import GUIEvent, EventBus

BASELINE_DPI = 96.0
CHANGE_THRESHOLD = 0.01  # 1%
DEBOUNCE_MS = 120

__all__ = ["DpiScalingService", "install_dpi_scaling_service"]


def _current_scale() -> float:
    app = QGuiApplication.instance()
    if not app:  # pragma: no cover - should not happen under normal runtime
        return 1.0
    screen = app.primaryScreen()
    if not screen:  # pragma: no cover
        return 1.0
    # Prefer logicalDotsPerInch for scaling UI metrics
    dpi = screen.logicalDotsPerInch() or BASELINE_DPI
    return round(dpi / BASELINE_DPI, 4)


@dataclass
class DpiScalingService(QObject):  # type: ignore[misc]
    _get_scale: Callable[[], float]
    _last_scale: float
    _debounce: QTimer

    def __init__(self, get_scale: Callable[[], float] = _current_scale) -> None:  # noqa: D401
        super().__init__()
        self._get_scale = get_scale
        self._last_scale = self._get_scale()
        self._debounce = QTimer(self)
        self._debounce.setInterval(DEBOUNCE_MS)
        self._debounce.setSingleShot(True)
        self._debounce.timeout.connect(self._emit_if_changed)  # type: ignore
        app = QGuiApplication.instance()
        if app:
            app.installEventFilter(self)
            try:
                app.primaryScreenChanged.connect(self._on_primary_screen_changed)  # type: ignore
            except Exception:  # pragma: no cover - older Qt versions
                pass

    # Qt hooks -----------------------------------------------------------------
    def eventFilter(self, watched: QObject, event: QEvent):  # noqa: D401
        if event.type() == QEvent.Type.ScreenChangeInternal:  # internal screen change
            self._debounce.start()
        return super().eventFilter(watched, event)

    def _on_primary_screen_changed(self, _screen):  # noqa: D401
        self._debounce.start()

    # Public API ---------------------------------------------------------------
    def current_scale(self) -> float:
        return self._last_scale

    # Internal -----------------------------------------------------------------
    def _emit_if_changed(self) -> None:
        new_scale = self._get_scale()
        if abs(new_scale - self._last_scale) / max(self._last_scale, 1e-6) <= CHANGE_THRESHOLD:
            return
        self._last_scale = new_scale
        try:
            bus = services.get_typed("event_bus", EventBus)
            bus.publish(GUIEvent.DPI_SCALE_CHANGED, {"scale": new_scale})
        except Exception:  # pragma: no cover - event bus missing
            pass


def install_dpi_scaling_service() -> DpiScalingService:
    svc = DpiScalingService()
    services.register("dpi_scaling", svc, allow_override=True)
    return svc
