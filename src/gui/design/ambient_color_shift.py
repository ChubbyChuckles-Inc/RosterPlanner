"""Ambient color shift developer feature (Milestone 5.10.33).

Provides a very low frequency hue rotation utility intended ONLY for
developer / experimental builds. When enabled (via environment variable
``APP_DEV_AMBIENT_COLOR_SHIFT=1`` or programmatic setter), code can query a
shifted color to apply to subtle gradient accents. The shift is disabled
automatically when reduced motion is enabled to respect accessibility.

Design Constraints:
 - No external dependencies (pure Python color conversion).
 - Safe fallbacks: if any parsing error occurs, return original color.
 - Testable: deterministic by passing explicit ``now`` timestamp.

Public API:
 - is_ambient_shift_enabled() -> bool
 - set_ambient_shift_enabled(enabled: bool) -> None
 - compute_shifted_hex(base_hex: str, *, now: float | None = None, period_seconds: float = 45.0, amplitude_degrees: float = 30.0) -> str

Behavior:
 - The hue rotates over time according to fraction f = (elapsed / period) % 1.0
 - Effective hue = base_hue + sin(2π f) * (amplitude_degrees / 2)
   (Using sine for gentle easing back and forth rather than full 0→amplitude wrap.)
 - If reduced motion is active or feature disabled: return base color unchanged.

Tests verify:
 - Disabled returns original color.
 - Enabled produces different color at quarter period.
 - Deterministic when passing explicit times.
 - Hex format (#RRGGBB) preserved.
"""

from __future__ import annotations

import math
import os
import time
from typing import Tuple

from .reduced_motion import is_reduced_motion

__all__ = [
    "is_ambient_shift_enabled",
    "set_ambient_shift_enabled",
    "compute_shifted_hex",
]

_enabled: bool | None = None  # tri-state: None => read from env


def is_ambient_shift_enabled() -> bool:
    global _enabled
    if _enabled is not None:
        return _enabled
    val = os.getenv("APP_DEV_AMBIENT_COLOR_SHIFT", "").strip().lower()
    _enabled = val in {"1", "true", "yes", "on"}
    return _enabled


def set_ambient_shift_enabled(enabled: bool) -> None:
    global _enabled
    _enabled = bool(enabled)


def _hex_to_rgb(color: str) -> Tuple[float, float, float]:
    if not (color.startswith("#") and len(color) == 7):
        raise ValueError("Expected #RRGGBB hex color")
    r = int(color[1:3], 16) / 255.0
    g = int(color[3:5], 16) / 255.0
    b = int(color[5:7], 16) / 255.0
    return r, g, b


def _rgb_to_hex(r: float, g: float, b: float) -> str:
    return "#" + "".join(f"{int(max(0, min(255, round(c * 255)))):02X}" for c in (r, g, b))


def _rgb_to_hsl(r: float, g: float, b: float) -> Tuple[float, float, float]:
    mx = max(r, g, b)
    mn = min(r, g, b)
    l = (mx + mn) / 2.0
    if mx == mn:
        return 0.0, 0.0, l
    d = mx - mn
    s = d / (2.0 - mx - mn) if l > 0.5 else d / (mx + mn)
    if mx == r:
        h = (g - b) / d + (6 if g < b else 0)
    elif mx == g:
        h = (b - r) / d + 2
    else:
        h = (r - g) / d + 4
    h /= 6
    return h * 360.0, s, l


def _hue_to_rgb(p, q, t):  # helper for hsl -> rgb
    if t < 0:
        t += 1
    if t > 1:
        t -= 1
    if t < 1 / 6:
        return p + (q - p) * 6 * t
    if t < 1 / 2:
        return q
    if t < 2 / 3:
        return p + (q - p) * (2 / 3 - t) * 6
    return p


def _hsl_to_rgb(h: float, s: float, l: float) -> Tuple[float, float, float]:
    h = (h % 360.0) / 360.0
    if s == 0:
        return l, l, l
    q = l * (1 + s) if l < 0.5 else l + s - l * s
    p = 2 * l - q
    r = _hue_to_rgb(p, q, h + 1 / 3)
    g = _hue_to_rgb(p, q, h)
    b = _hue_to_rgb(p, q, h - 1 / 3)
    return r, g, b


def compute_shifted_hex(
    base_hex: str,
    *,
    now: float | None = None,
    period_seconds: float = 45.0,
    amplitude_degrees: float = 30.0,
) -> str:
    """Return ambient-shifted hex color or original when disabled.

    Parameters
    ----------
    base_hex: #RRGGBB color to shift.
    now: float | None
        Timestamp (seconds). Defaults to time.monotonic() for live updates.
    period_seconds: float
        Full oscillation period for one back-and-forth cycle.
    amplitude_degrees: float
        Peak-to-peak range is amplitude / 2 each direction from base.
    """
    try:
        if not is_ambient_shift_enabled() or is_reduced_motion():
            return base_hex
        if period_seconds <= 0 or amplitude_degrees <= 0:
            return base_hex
        ts = time.monotonic() if now is None else now
        r, g, b = _hex_to_rgb(base_hex)
        h, s, l = _rgb_to_hsl(r, g, b)
        # Oscillate around base hue with sine wave
        phase = (ts / period_seconds) % 1.0
        delta = math.sin(phase * 2 * math.pi) * (amplitude_degrees / 2.0)
        new_h = h + delta
        nr, ng, nb = _hsl_to_rgb(new_h, s, l)
        return _rgb_to_hex(nr, ng, nb)
    except Exception:  # pragma: no cover - safety net
        return base_hex
