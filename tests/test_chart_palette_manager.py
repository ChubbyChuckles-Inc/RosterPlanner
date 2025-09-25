"""Tests for ChartPaletteManager (Milestone 7.2)."""

from __future__ import annotations

from dataclasses import dataclass

from gui.charting.palette import ChartPaletteManager
from gui.services.event_bus import EventBus, GUIEvent
from gui.services.service_locator import services


@dataclass
class _FakeThemeService:
    _cached_map: dict


def _setup(theme_map):
    services.register("event_bus", EventBus(), allow_override=True)
    services.register("theme_service", _FakeThemeService(theme_map), allow_override=True)


def test_initial_palette_derivation():
    _setup(
        {
            "text.primary": "#111111",
            "background.secondary": "#DDDDDD",
            "surface.card": "#FFFFFF",
            "background.primary": "#FAFAFA",
            "accent.base": "#123456",
        }
    )
    mgr = ChartPaletteManager()
    snap = mgr.palette_snapshot()
    assert snap["axis.text"] == "#111111"
    assert snap["series.0"] == "#123456"


def test_palette_updates_on_theme_change():
    _setup(
        {
            "text.primary": "#222222",
            "background.secondary": "#CCCCCC",
            "surface.card": "#FFFFFF",
            "background.primary": "#FAFAFA",
            "accent.base": "#AA0000",
        }
    )
    mgr = ChartPaletteManager()
    first_series0 = mgr.color_for_series(0)
    # mutate theme accent and emit event
    theme = services.get("theme_service")
    theme._cached_map["accent.base"] = "#00AA00"  # type: ignore[attr-defined]
    services.get("event_bus").publish(GUIEvent.THEME_CHANGED, {"changed": 1, "count": 1})
    second_series0 = mgr.color_for_series(0)
    assert first_series0 != second_series0
