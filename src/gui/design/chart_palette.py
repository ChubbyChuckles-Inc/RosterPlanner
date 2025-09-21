"""Adaptive chart color palette utilities (Milestone 0.14 partial).

The goal is to provide semantic color roles for chart rendering that adapt to the
overall design tokens (dark / high contrast). This initial implementation derives
colors from existing accent & surface tokens to guarantee consistency and contrast.

Semantic Roles Provided (ChartPalette):
 - background: chart plotting area background
 - grid_major: primary grid line color
 - grid_minor: secondary grid line color
 - series: ordered list of categorical series colors
 - series_muted: lighter variant list for highlight layering / hover dimming
 - alert_positive / alert_negative / alert_neutral: used for threshold & annotation markers

Derivation Strategy:
 - Use background.surface.secondary as base plotting background (sufficiently neutral).
 - Grid lines: derive by blending text.muted with background (major) and increasing transparency
   for minor (represented here by hex adjustment). For simplicity (and to avoid runtime alpha
   composition complexity), we lighten/darken via a simple channel interpolation.
 - Series colors: start with accent.primary, then generate additional distinct hues by rotating
   through accent.success, accent.info, accent.warning, accent.error plus a desaturated variant.
 - Muted series variants: lighten each base series color toward text.secondary.

NOTE: A future extension may incorporate dynamic palette generation (e.g., HCL interpolation) and
contrast guarantees. For now we apply a contrast check in tests for grid vs background.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import List

from .loader import DesignTokens
from .contrast import contrast_ratio

__all__ = ["ChartPalette", "build_chart_palette"]


@dataclass(frozen=True)
class ChartPalette:
    background: str
    grid_major: str
    grid_minor: str
    series: List[str]
    series_muted: List[str]
    alert_positive: str
    alert_negative: str
    alert_neutral: str


def _hex_to_rgb(h: str) -> tuple[int, int, int]:
    h = h.lstrip("#")
    return int(h[0:2], 16), int(h[2:4], 16), int(h[4:6], 16)


def _rgb_to_hex(rgb: tuple[int, int, int]) -> str:
    return "#" + "".join(f"{c:02x}" for c in rgb)


def _blend(src: str, dst: str, t: float) -> str:
    sr, sg, sb = _hex_to_rgb(src)
    dr, dg, db = _hex_to_rgb(dst)
    return _rgb_to_hex(
        (
            int(sr + (dr - sr) * t + 0.5),
            int(sg + (dg - sg) * t + 0.5),
            int(sb + (db - sb) * t + 0.5),
        )
    )


def build_chart_palette(tokens: DesignTokens) -> ChartPalette:
    bg = tokens.color("surface", "secondary")
    text_muted = tokens.color("text", "muted")
    text_secondary = tokens.color("text", "secondary")
    # Grid derivation
    grid_major = _blend(text_muted, bg, 0.65)  # pull towards bg to reduce dominance
    grid_minor = _blend(grid_major, bg, 0.55)
    # Series base colors (reuse existing accent semantic variety)
    series_candidates = [
        tokens.color("accent", "primary"),
        tokens.color("accent", "success"),
        tokens.color("accent", "info"),
        tokens.color("accent", "warning"),
        tokens.color("accent", "error"),
    ]
    # Add a desaturated variant (blend success+info)
    series_candidates.append(_blend(series_candidates[1], series_candidates[2], 0.5))
    # Build muted variants by blending toward secondary text
    series_muted = [_blend(c, text_secondary, 0.4) for c in series_candidates]
    palette = ChartPalette(
        background=bg,
        grid_major=grid_major,
        grid_minor=grid_minor,
        series=series_candidates,
        series_muted=series_muted,
        alert_positive=tokens.color("accent", "success"),
        alert_negative=tokens.color("accent", "error"),
        alert_neutral=tokens.color("accent", "info"),
    )
    # Basic contrast sanity: major grid vs background should be >=1.3 (visual separation in dark theme)
    if (
        contrast_ratio(palette.grid_major, palette.background) < 1.3
    ):  # pragma: no cover (defensive path)
        # Fallback: force lighten relative to background by mixing with text.secondary
        palette = ChartPalette(
            background=palette.background,
            grid_major=_blend(text_secondary, bg, 0.55),
            grid_minor=_blend(text_secondary, bg, 0.7),
            series=palette.series,
            series_muted=palette.series_muted,
            alert_positive=palette.alert_positive,
            alert_negative=palette.alert_negative,
            alert_neutral=palette.alert_neutral,
        )
    return palette
