"""Heatmap color ramp perceptual uniformity validation (Milestone 0.48).

Objective: ensure a supplied ordered ramp of token keys (e.g., low→high data
intensity) exhibits approximately monotonic perceptual lightness progression
to avoid misleading gradients or false clustering artifacts.

Approach
--------
1. Resolve each token key to a hex color via provided theme map.
2. Convert hex -> sRGB -> approximate CIE Lab (L component only) using a
   simple D65-adapted transform (sufficient for monotonic checks; full a/b not required).
3. Compute successive L deltas; check signs for monotonicity (allow a small
   tolerance jitter).
4. Report statistics: min/max L, average delta, standard deviation of L deltas,
   number of direction reversals, and any missing tokens.
5. Return structured report dataclass making it easy for tests or future UI.

Tolerances
----------
 - Small jitter threshold: absolute delta < 0.75 treated as neutral (ignored in reversal count)
 - Accept overall if: no direction reversals > jitter threshold AND total length >= 3.

Limitations
-----------
 - Not a full perceptual deltaE uniformity validation (future enhancement could sample midpoints)
 - Ignores hue shifts; focuses purely on luminance ordering.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import List, Mapping, Sequence, Tuple
import math

from .color_mixing import parse_hex

__all__ = ["HeatmapRampReport", "validate_heatmap_ramp"]


@dataclass(frozen=True)
class HeatmapRampReport:
    ramp_keys: Tuple[str, ...]
    resolved_colors: Tuple[str, ...]
    lightness_values: Tuple[float, ...]
    deltas: Tuple[float, ...]
    reversals: int
    missing: Tuple[str, ...]
    average_delta: float
    delta_stddev: float
    min_L: float
    max_L: float
    uniform: bool
    message: str

    def summary(self) -> str:  # pragma: no cover simple convenience
        return (
            f"HeatmapRampReport: len={len(self.ramp_keys)} uniform={self.uniform} "
            f"reversals={self.reversals} avgΔ={self.average_delta:.2f} sdΔ={self.delta_stddev:.2f}"
        )


def _srgb_to_linear(c: float) -> float:
    if c <= 0.04045:
        return c / 12.92
    return ((c + 0.055) / 1.055) ** 2.4


def _rgb_to_lab_L(r: int, g: int, b: int) -> float:
    # Normalize
    r_lin = _srgb_to_linear(r / 255.0)
    g_lin = _srgb_to_linear(g / 255.0)
    b_lin = _srgb_to_linear(b / 255.0)
    # Convert to XYZ (D65) using sRGB matrix
    X = r_lin * 0.4123908 + g_lin * 0.3575843 + b_lin * 0.1804808
    Y = r_lin * 0.2126390 + g_lin * 0.7151687 + b_lin * 0.0721923
    Z = r_lin * 0.0193308 + g_lin * 0.1191948 + b_lin * 0.9505322
    # Normalize by reference white (D65) Xn, Yn, Zn
    Xn, Yn, Zn = 0.95047, 1.0, 1.08883
    xr, yr, zr = X / Xn, Y / Yn, Z / Zn

    def f(t: float) -> float:
        return t ** (1 / 3) if t > 0.008856 else (7.787 * t) + (16 / 116)

    L = 116 * f(yr) - 16  # We only need L.
    return L


def validate_heatmap_ramp(
    ramp_keys: Sequence[str], theme_map: Mapping[str, str], *, jitter_threshold: float = 0.75
) -> HeatmapRampReport:
    missing: List[str] = []
    resolved: List[str] = []
    lightness: List[float] = []
    for key in ramp_keys:
        color = theme_map.get(key)
        if not color:
            missing.append(key)
            # Skip unresolved tokens from lightness calc but keep placeholder for alignment
            continue
        try:
            r, g, b, _ = parse_hex(color)
            L = _rgb_to_lab_L(r, g, b)
            resolved.append(color.lower())
            lightness.append(L)
        except Exception:  # pragma: no cover (parse errors unlikely given existing tokens)
            missing.append(key)

    deltas: List[float] = []
    reversals = 0
    for i in range(1, len(lightness)):
        d = lightness[i] - lightness[i - 1]
        deltas.append(d)
    # Determine predominant direction (ignore jitter deltas)
    significant = [d for d in deltas if abs(d) >= jitter_threshold]
    direction = 0
    for d in significant:
        if d > 0:
            direction = 1
            break
        if d < 0:
            direction = -1
            break
    if direction != 0:
        for d in significant:
            if (d > 0 and direction < 0) or (d < 0 and direction > 0):
                reversals += 1
                # Once reversal counted, we could flip direction or keep counting further conflicts
    avg_delta = sum(abs(d) for d in deltas) / len(deltas) if deltas else 0.0
    if deltas:
        mean = sum(deltas) / len(deltas)
        var = sum((d - mean) ** 2 for d in deltas) / len(deltas)
        stddev = math.sqrt(var)
    else:
        stddev = 0.0

    if missing:
        uniform = False
        msg = f"Missing {len(missing)} tokens; cannot validate fully"
    elif len(lightness) < 3:
        uniform = False
        msg = "Ramp too short for validation (<3 resolved colors)"
    else:
        uniform = reversals == 0
        msg = "Monotonic lightness progression" if uniform else "Lightness reversals detected"

    report = HeatmapRampReport(
        ramp_keys=tuple(ramp_keys),
        resolved_colors=tuple(resolved),
        lightness_values=tuple(lightness),
        deltas=tuple(deltas),
        reversals=reversals,
        missing=tuple(missing),
        average_delta=avg_delta,
        delta_stddev=stddev,
        min_L=min(lightness) if lightness else 0.0,
        max_L=max(lightness) if lightness else 0.0,
        uniform=uniform,
        message=msg,
    )
    return report
