"""Color Vision Deficiency Simulation Utilities (Milestone 5.10.36).

Implements lightweight matrix-based approximations for simulating
protanopia and deuteranopia transformations for sRGB colors. These are
not clinically perfect but sufficient for developer accessibility audits.

Approach:
 - Parse hex -> linear RGB
 - Apply 3x3 deficiency matrix (values derived from common simulation
   approximations; see Brettel/Viénot-inspired simplified model)
 - Convert back to hex (gamma re-applied)

Public API:
 - simulate_hex(color: str, mode: str | None) -> str
 - transform_palette(palette: Mapping[str, str], mode: str | None) -> dict[str,str]

Integration Path:
 ThemeService can call `apply_color_vision_filter_if_active` to overlay
 simulated colors onto its `_cached_map` when color blind mode service
 is active.
"""

from __future__ import annotations

from typing import Mapping, Dict
import math

__all__ = [
    "simulate_hex",
    "transform_palette",
    "apply_color_vision_filter_if_active",
]

_MATRICES = {
    # Simplified deficiency matrices (approximation)
    "protanopia": (
        (0.0, 1.05118294, -0.05116099),
        (0.0, 1.0, 0.0),
        (0.0, 0.0, 1.0),
    ),
    "deuteranopia": (
        (1.0, 0.0, 0.0),
        (0.9513092, 0.0, 0.04866992),
        (0.0, 0.0, 1.0),
    ),
}


def _hex_to_rgb(c: str):
    if not c or not c.startswith("#") or len(c) not in (7, 4):
        raise ValueError("Invalid hex color")
    if len(c) == 4:  # #RGB
        r = int(c[1] * 2, 16)
        g = int(c[2] * 2, 16)
        b = int(c[3] * 2, 16)
    else:
        r = int(c[1:3], 16)
        g = int(c[3:5], 16)
        b = int(c[5:7], 16)
    return r, g, b


def _rgb_to_hex(r: int, g: int, b: int) -> str:
    return f"#{r:02X}{g:02X}{b:02X}"


def _srgb_to_linear(v: float) -> float:
    v /= 255.0
    return v / 12.92 if v <= 0.04045 else ((v + 0.055) / 1.055) ** 2.4


def _linear_to_srgb(v: float) -> int:
    v = max(0.0, min(1.0, v))
    if v <= 0.0031308:
        v = 12.92 * v
    else:
        v = 1.055 * (v ** (1 / 2.4)) - 0.055
    return int(round(v * 255))


def simulate_hex(color: str, mode: str | None) -> str:
    """Return simulated color; passthrough if mode is None or unsupported."""
    if mode not in _MATRICES:
        return color
    try:
        r, g, b = _hex_to_rgb(color)
        lr, lg, lb = map(_srgb_to_linear, (r, g, b))
        m = _MATRICES[mode]
        nr = lr * m[0][0] + lg * m[0][1] + lb * m[0][2]
        ng = lr * m[1][0] + lg * m[1][1] + lb * m[1][2]
        nb = lr * m[2][0] + lg * m[2][1] + lb * m[2][2]
        return _rgb_to_hex(_linear_to_srgb(nr), _linear_to_srgb(ng), _linear_to_srgb(nb))
    except Exception:
        return color


def transform_palette(palette: Mapping[str, str], mode: str | None) -> Dict[str, str]:
    if not mode:
        return dict(palette)
    out: Dict[str, str] = {}
    for k, v in palette.items():
        if isinstance(v, str) and v.startswith("#"):
            out[k] = simulate_hex(v, mode)
        else:
            out[k] = v
    return out


def apply_color_vision_filter_if_active(colors: Dict[str, str], mode: str | None) -> None:
    """In-place transformation of a color map given an active simulation mode."""
    if not mode:
        return
    transformed = transform_palette(colors, mode)
    colors.clear()
    colors.update(transformed)
