"""Elevation shadow utility (Milestone 5.10.2).

Provides a mapping from elevation token levels to QSS-friendly shadow style
snippets. Qt Widgets do not support native CSS `box-shadow`, so we emulate
shadow layers where possible using QGraphicsDropShadowEffect or by exposing
helper methods that apply effects. For now we:

- Offer `get_shadow_effect(level)` returning a configured QGraphicsDropShadowEffect.
- Provide `apply_elevation(widget, level)` convenience to attach effect.
- Validate requested level against design tokens.

This keeps the logic testable; a unit test will exercise level mapping and
verify stable parameters. Visual regression / screenshot tests can come later
(Milestone 5.10.63).
"""

from __future__ import annotations

from typing import Dict
from enum import Enum
from PyQt6.QtWidgets import QWidget, QGraphicsDropShadowEffect
from PyQt6.QtGui import QColor

try:  # Token loading optional for early bootstrap
    from .loader import load_tokens
except Exception:  # pragma: no cover
    load_tokens = None  # type: ignore

# Default fallback levels if tokens unavailable
_FALLBACK_LEVELS: Dict[int, Dict[str, int | float]] = {
    0: {"blur": 0, "x": 0, "y": 0, "alpha": 0},
    1: {"blur": 8, "x": 0, "y": 2, "alpha": 60},
    2: {"blur": 12, "x": 0, "y": 4, "alpha": 70},
    3: {"blur": 18, "x": 0, "y": 6, "alpha": 80},
    4: {"blur": 24, "x": 0, "y": 8, "alpha": 90},
}


def _load_elevation_levels() -> Dict[int, Dict[str, int | float]]:
    try:
        if load_tokens is None:
            return _FALLBACK_LEVELS
        tokens = load_tokens()
        raw = tokens.raw.get("elevation", {})
        # Map token numeric value to a heuristic shadow spec; the token value itself is kept as key
        levels: Dict[int, Dict[str, int | float]] = {}
        for k, v in raw.items():
            if not isinstance(v, int):
                continue
            # Heuristic: blur = 6 + v*6, y-offset = 2 + v*2, alpha = 50 + v*10
            levels[v] = {
                "blur": 6 + v * 6,
                "x": 0,
                "y": 2 + v * 2,
                "alpha": min(110, 50 + v * 10),
            }
        # Ensure fallback if empty
        return levels or _FALLBACK_LEVELS
    except Exception:  # pragma: no cover - defensive
        return _FALLBACK_LEVELS


_ELEVATION_LEVELS = _load_elevation_levels()


class ElevationRole(Enum):
    """Semantic elevation roles used across the application.

    This indirection prevents ad‑hoc numeric usage sprinkled through the
    codebase. If design later rebalances depth scale we only modify this file.
    """

    FLAT = "flat"  # No shadow
    PRIMARY_DOCK = "primary_dock"  # Core structural docks (navigation, availability)
    SECONDARY_DOCK = "secondary_dock"  # Supplemental panels (logs, stats, detail, planner, recent)
    FLOATING_DOCK = "floating_dock"  # Dock when detached / floating
    OVERLAY = "overlay"  # Future modal/overlay panels


# Central mapping of role -> elevation level integer
ELEVATION_ROLE_LEVEL: Dict[ElevationRole, int] = {
    ElevationRole.FLAT: 0,
    ElevationRole.SECONDARY_DOCK: 1,
    ElevationRole.PRIMARY_DOCK: 2,
    ElevationRole.FLOATING_DOCK: 3,
    ElevationRole.OVERLAY: 4,
}


def get_shadow_effect(level: int) -> QGraphicsDropShadowEffect:
    if level not in _ELEVATION_LEVELS:
        # Fallback to nearest smaller, else 0
        candidates = [l for l in _ELEVATION_LEVELS.keys() if l <= level]
        level = max(candidates) if candidates else 0
    spec = _ELEVATION_LEVELS[level]
    effect = QGraphicsDropShadowEffect()
    effect.setBlurRadius(int(spec["blur"]))
    effect.setOffset(int(spec["x"]), int(spec["y"]))
    # Shadow color uses surface.primary text inverted; simple dark RGBA overlay for now
    color = QColor(0, 0, 0, int(spec["alpha"]))
    effect.setColor(color)
    return effect


def apply_elevation(widget: QWidget, level: int) -> None:
    """Apply a numeric elevation level to a widget.

    Level 0 clears any existing shadow for clarity (rather than attaching an
    invisible effect) to minimize QWidget effect overhead.
    """
    if level <= 0:
        try:
            widget.setGraphicsEffect(None)  # type: ignore[arg-type]
        except Exception:  # pragma: no cover - defensive
            pass
        return
    effect = get_shadow_effect(level)
    widget.setGraphicsEffect(effect)  # type: ignore[arg-type]


def apply_elevation_role(widget: QWidget, role: ElevationRole) -> None:
    """Apply elevation using a semantic role.

    Args:
        widget: Target widget (typically QDockWidget instance).
        role: ElevationRole indicating semantic depth intent.
    """
    level = ELEVATION_ROLE_LEVEL.get(role, 0)
    apply_elevation(widget, level)


def current_role_level(role: ElevationRole) -> int:
    """Expose current mapped numeric level (used for tests)."""
    return ELEVATION_ROLE_LEVEL[role]


__all__ = [
    "apply_elevation",
    "get_shadow_effect",
    "apply_elevation_role",
    "ElevationRole",
    "current_role_level",
    "ELEVATION_ROLE_LEVEL",
]
