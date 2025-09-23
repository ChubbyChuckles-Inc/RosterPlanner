"""Variable font integration utility (Milestone 5.10.25).

Provides a thin abstraction for requesting a `QFont` with variable axes
adjustments (currently weight axis only, placeholder for optical size `opsz`).

Rationale: Centralizing axis manipulation enables consistent typography
transitions (future smooth animations) and isolates platform differences if
some axes are unsupported in certain builds of Qt.

Design Decisions:
 - Avoid external dependencies; rely on standard PyQt6 `QFont` API.
 - If requested weight is not supported, fallback to nearest standard step.
 - Provide `describe_variable_support()` for diagnostics & testing.
 - Provide `interpolate_weight()` helper returning clamped user-friendly value.

Usage:
    f = variable_font("Primary", weight=520)
    label.setFont(f)
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Optional, Tuple
from PyQt6.QtGui import QFontDatabase, QFont

__all__ = [
    "variable_font",
    "describe_variable_support",
    "interpolate_weight",
    "VariableFontSupport",
]


@dataclass(frozen=True)
class VariableFontSupport:
    family: str
    has_variable_weight: bool
    weight_range: Tuple[int, int]
    note: str = ""


def describe_variable_support(family: str) -> VariableFontSupport:
    # Use static QFontDatabase methods (construction can fail in some headless builds)
    try:
        weights = QFontDatabase.weights(family)  # type: ignore[attr-defined]
    except Exception:
        weights = []
    if not weights:
        return VariableFontSupport(family, False, (400, 700), note="No weights detected")
    try:
        w_min = min(weights)
        w_max = max(weights)
    except Exception:
        return VariableFontSupport(family, False, (400, 700), note="Invalid weights list")
    has_var = len(weights) >= 5
    return VariableFontSupport(family, has_var, (w_min, w_max))


def interpolate_weight(target: int, support: VariableFontSupport) -> int:
    lo, hi = support.weight_range
    if target < lo:
        return lo
    if target > hi:
        return hi
    if not support.has_variable_weight:
        # Snap to nearest common step (Thin 100, Light 300, Normal 400, Medium 500, Bold 700, Black 900)
        steps = [100, 200, 300, 400, 500, 600, 700, 800, 900]
        return min(steps, key=lambda s: abs(s - target))
    return target


def variable_font(family: str, *, weight: int = 400, pixel_size: Optional[int] = None) -> QFont:
    support = describe_variable_support(family)
    effective_weight = interpolate_weight(weight, support)
    f = QFont(family)
    if pixel_size is not None:
        f.setPixelSize(pixel_size)
    # Qt weight is an enum; direct int mapping allowed in PyQt6.
    f.setWeight(effective_weight)  # type: ignore[arg-type]
    return f
