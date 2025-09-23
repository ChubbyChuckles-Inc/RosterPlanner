"""Neutral Ramp Delta-E Calibration (Milestone 5.10.47).

Provides a helper to evaluate perceptual uniformity of a neutral (grayscale /
near-gray) ramp of token colors. Ensures adjacent steps have sufficient
contrast separation (delta-E >= min_delta) while avoiding large visual jumps
(delta-E <= max_delta).

We use sRGB -> CIE Lab conversion (D65) with the CIE76 delta-E formula which is
sufficient for relative uniformity checks here (more advanced formulas like
CIEDE2000 are heavier and unnecessary for a coarse validation gate).

API:
    report = validate_neutral_ramp(["#111111","#1E1E1E",...])
    if not report.ok:
        for issue in report.issues: ...

Design choices:
 - Pure Python, no external color libraries (keeps dependency surface small).
 - Graceful degradation: invalid hex entries are reported but do not crash.
 - Provide structured report object for future integration in design CI.
"""

from __future__ import annotations
from dataclasses import dataclass
from typing import List, Sequence
import math

__all__ = [
    "NeutralRampIssue",
    "NeutralRampReport",
    "delta_e",
    "srgb_to_lab",
    "validate_neutral_ramp",
]


@dataclass(frozen=True)
class NeutralRampIssue:
    index: int  # position of the *second* color in the pair
    delta_e: float
    kind: str  # "too_small" | "too_large" | "invalid_hex"
    message: str


@dataclass(frozen=True)
class NeutralRampReport:
    ok: bool
    issues: List[NeutralRampIssue]
    deltas: List[float]

    def summary(self) -> str:
        if self.ok:
            return f"Neutral ramp OK ({len(self.deltas)} deltas, range={min(self.deltas):.2f}-{max(self.deltas):.2f})"
        return "Neutral ramp issues: " + ", ".join(
            f"#{i}:{k}({d:.2f})"
            for i, d, k in [(iss.index, iss.delta_e, iss.kind) for iss in self.issues]
        )


def _srgb_channel_to_linear(c: float) -> float:
    c = c / 255.0
    return c / 12.92 if c <= 0.04045 else ((c + 0.055) / 1.055) ** 2.4


def srgb_to_lab(hex_color: str) -> tuple[float, float, float]:
    if not (hex_color.startswith("#") and len(hex_color) == 7):
        raise ValueError("invalid hex")
    r = int(hex_color[1:3], 16)
    g = int(hex_color[3:5], 16)
    b = int(hex_color[5:7], 16)
    r_lin = _srgb_channel_to_linear(r)
    g_lin = _srgb_channel_to_linear(g)
    b_lin = _srgb_channel_to_linear(b)
    # sRGB to XYZ (D65)
    X = r_lin * 0.4124 + g_lin * 0.3576 + b_lin * 0.1805
    Y = r_lin * 0.2126 + g_lin * 0.7152 + b_lin * 0.0722
    Z = r_lin * 0.0193 + g_lin * 0.1192 + b_lin * 0.9505
    # Normalize for D65 white
    Xn, Yn, Zn = 0.95047, 1.0, 1.08883

    def f(t: float) -> float:
        return t ** (1 / 3) if t > 0.008856 else (7.787 * t) + (16 / 116)

    fx = f(X / Xn)
    fy = f(Y / Yn)
    fz = f(Z / Zn)
    L = (116 * fy) - 16
    a = 500 * (fx - fy)
    b_val = 200 * (fy - fz)
    return L, a, b_val


def delta_e(lab1: tuple[float, float, float], lab2: tuple[float, float, float]) -> float:
    return math.sqrt(sum((a - b) ** 2 for a, b in zip(lab1, lab2)))


def validate_neutral_ramp(
    colors: Sequence[str],
    *,
    min_delta: float = 1.5,
    max_delta: float = 12.0,
) -> NeutralRampReport:
    issues: List[NeutralRampIssue] = []
    deltas: List[float] = []
    last_lab = None
    for idx, col in enumerate(colors):
        try:
            lab = srgb_to_lab(col)
        except Exception:
            issues.append(
                NeutralRampIssue(
                    index=idx,
                    delta_e=0.0,
                    kind="invalid_hex",
                    message=f"Invalid hex at position {idx}: {col}",
                )
            )
            last_lab = None
            continue
        if last_lab is not None:
            d = delta_e(last_lab, lab)
            deltas.append(d)
            if d < min_delta:
                issues.append(
                    NeutralRampIssue(
                        index=idx,
                        delta_e=d,
                        kind="too_small",
                        message=f"Delta-E {d:.2f} below minimum {min_delta}",
                    )
                )
            elif d > max_delta:
                issues.append(
                    NeutralRampIssue(
                        index=idx,
                        delta_e=d,
                        kind="too_large",
                        message=f"Delta-E {d:.2f} exceeds maximum {max_delta}",
                    )
                )
        last_lab = lab
    ok = not issues
    if not deltas:
        # Single color or all invalid -> treat as failure
        if ok:
            ok = False
            issues.append(
                NeutralRampIssue(
                    index=0, delta_e=0.0, kind="too_small", message="Insufficient colors for ramp"
                )
            )
    return NeutralRampReport(ok=ok, issues=issues, deltas=deltas)
