"""Theme-aware chart palette manager (Milestone 7.2).

Provides semantic color roles for charts that adapt automatically when the
application theme changes (listens to GUIEvent.THEME_CHANGED via EventBus).

Exposed roles (initial minimal set):
 - series.n (ordinal series colors)
 - axis.text
 - axis.line
 - grid.line
 - background.plot
 - background.figure

Design:
 - Pulls from ThemeService semantic colors with graceful fallbacks.
 - Keeps an internal cached palette dict so repeated lookups are O(1) without
   repeatedly touching the theme service mapping.
 - Emits no events itself; view layer or chart builders ask for colors.

Test Strategy:
 - Use a fake ThemeService + EventBus to simulate theme change and ensure
   palette updates (series color changes propagate).
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Dict, List

from gui.services.event_bus import GUIEvent, EventBus
from gui.services.service_locator import services

SERIES_FALLBACK = [
    "#4E79A7",
    "#F28E2B",
    "#E15759",
    "#76B7B2",
    "#59A14F",
    "#EDC948",
    "#B07AA1",
    "#FF9DA7",
]


@dataclass
class ChartPaletteManager:
    """Derives chart palette from ThemeService and updates on theme changes."""

    _cache: Dict[str, str] = field(default_factory=dict)
    _series_colors: List[str] = field(default_factory=list)

    def __post_init__(self) -> None:  # Load initial palette
        self._rebuild()
        bus: EventBus | None = services.try_get("event_bus")
        if bus:
            bus.subscribe(GUIEvent.THEME_CHANGED, self._on_theme_changed)

    # Public API ------------------------------------------------------
    def color_for_series(self, index: int) -> str:
        if index < 0:
            index = 0
        if not self._series_colors:
            self._series_colors = SERIES_FALLBACK
        return self._series_colors[index % len(self._series_colors)]

    def role(self, key: str, default: str | None = None) -> str | None:
        return self._cache.get(key, default)

    def palette_snapshot(self) -> Dict[str, str]:
        snap = dict(self._cache)
        for i, c in enumerate(self._series_colors):
            snap[f"series.{i}"] = c
        return snap

    # Internal --------------------------------------------------------
    def _on_theme_changed(self, _evt) -> None:  # pragma: no cover - trivial wrapper
        self._rebuild()

    def _rebuild(self) -> None:
        theme = services.try_get("theme_service")
        colors = getattr(theme, "_cached_map", {}) if theme else {}
        # Build roles with fallbacks
        self._cache = {
            "axis.text": colors.get("text.primary", "#222222"),
            "axis.line": colors.get("background.secondary", "#CCCCCC"),
            "grid.line": colors.get("background.secondary", "#E0E0E0"),
            "background.plot": colors.get("surface.card", "#FFFFFF"),
            "background.figure": colors.get("background.primary", "#FFFFFF"),
        }
        accent = colors.get("accent.base") or "#4E79A7"
        # Derive series palette by rotating hue approximations: we just tint accent for now
        # Simple deterministic variations by mixing with fallback palette
        base_list = SERIES_FALLBACK
        self._series_colors = [accent] + [c for c in base_list if c.lower() != accent.lower()][:7]


def get_chart_palette_manager() -> ChartPaletteManager:
    mgr = services.try_get("chart_palette")
    if mgr is None:
        mgr = ChartPaletteManager()
        services.register("chart_palette", mgr)
    return mgr

__all__ = ["ChartPaletteManager", "get_chart_palette_manager"]
