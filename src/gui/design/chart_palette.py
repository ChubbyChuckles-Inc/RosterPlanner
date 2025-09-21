"""Adaptive chart color palette utilities (Milestone 0.14 complete).

Provides semantic color roles for chart rendering that adapt to design tokens
and support both default and high-contrast variants. The palette builder is
pure (no Qt imports) and deterministic given tokens + parameters.

Semantic roles (``ChartPalette``):
 - ``background``: plotting area background
 - ``grid_major`` / ``grid_minor``: grid line colors with sufficient but subtle separation
 - ``series``: categorical series colors (length configurable)
 - ``series_muted``: softened counterparts for hover dim, de-emphasis or stacked overlays
 - ``alert_positive`` / ``alert_negative`` / ``alert_neutral``: threshold / annotation markers

Key features:
 - Dynamic series count (request N; will generate at least N distinct-ish colors)
 - High contrast adaptation: derives from high-contrast token groups when active
 - Defensive contrast fallback for grid lines
 - Stable ordering: first 5 map to accent semantic roles for recognizability

Design choices:
 - Minimal custom color math: simple RGB interpolation to keep Python 3.8 compatibility
 - Avoid reliance on external color libraries (can be revisited if HCL/Lab needed later)
 - Deterministic hashing/rotation of base accents for extended series beyond semantic seeds

Future extensions (not yet implemented):
 - Perceptual color spacing in OKLCH / CIELAB
 - Contrast guarantees between adjacent series (pairwise delta-E threshold)
 - Light theme variant once light tokens introduced
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import List, Iterable

from .loader import DesignTokens
from .contrast import contrast_ratio

__all__ = ["ChartPalette", "build_chart_palette"]


@dataclass(frozen=True)
class ChartPalette:
    """Immutable collection of semantic chart colors.

    Attributes
    ----------
    background : str
        Hex color for plot background (#RRGGBB).
    grid_major / grid_minor : str
        Grid line colors. Minor is visually lighter / closer to background.
    series : list[str]
        Base categorical series colors (length depends on request).
    series_muted : list[str]
        Muted counterparts blended toward secondary text color.
    alert_positive / alert_negative / alert_neutral : str
        Status / annotation hues (success, error, info).
    """

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


def _cycle(seed: Iterable[str], count: int) -> List[str]:
    base = list(seed)
    if not base:
        return []
    out: List[str] = []
    i = 0
    # Simple rotation; for additional cycles we progressively blend with primary accent
    primary = base[0]
    round_idx = 0
    while len(out) < count:
        color = base[i % len(base)]
        if round_idx > 0:
            # Each additional pass moves 15% closer to primary accent to create a tonal family
            color = _blend(color, primary, min(0.15 * round_idx, 0.6))
        out.append(color)
        i += 1
        if i % len(base) == 0:
            round_idx += 1
    return out


def build_chart_palette(
    tokens: DesignTokens,
    *,
    series_count: int = 8,
    variant: str = "default",
) -> ChartPalette:
    """Build an adaptive chart palette.

    Parameters
    ----------
    tokens : DesignTokens
        Loaded design tokens.
    series_count : int, default 8
        Desired number of categorical series colors. Will be clamped >= 1.
    variant : str, default "default"
        Visual variant ("default" or "high-contrast"). If high-contrast is
        requested but not supported by tokens, falls back silently.
    """
    if series_count < 1:
        series_count = 1

    # Choose background referencing surface tokens (secondary gives neutral contrast).
    bg = tokens.color("surface", "secondary")
    text_muted = tokens.color("text", "muted")
    text_secondary = tokens.color("text", "secondary")

    # Grid derivation: start from muted text blended toward background.
    grid_major = _blend(text_muted, bg, 0.65)
    grid_minor = _blend(grid_major, bg, 0.55)

    # High contrast tweak: if variant requested and supported, pull grid a bit closer to text
    if variant == "high-contrast" and tokens.is_high_contrast_supported():
        grid_major = _blend(text_muted, bg, 0.5)  # increase contrast
        grid_minor = _blend(grid_major, bg, 0.6)

    # Base semantic accent seeds; stable first positions.
    seeds = [
        tokens.color("accent", "primary"),
        tokens.color("accent", "success"),
        tokens.color("accent", "info"),
        tokens.color("accent", "warning"),
        tokens.color("accent", "error"),
    ]
    # Add a mid blend of success+info to diversify early palette if needed.
    seeds.append(_blend(seeds[1], seeds[2], 0.5))

    series_all = _cycle(seeds, series_count)

    # Muted variants for layering (40% toward secondary text keeps hue recognizable).
    series_muted = [_blend(c, text_secondary, 0.4) for c in series_all]

    palette = ChartPalette(
        background=bg,
        grid_major=grid_major,
        grid_minor=grid_minor,
        series=series_all,
        series_muted=series_muted,
        alert_positive=tokens.color("accent", "success"),
        alert_negative=tokens.color("accent", "error"),
        alert_neutral=tokens.color("accent", "info"),
    )

    # Defensive contrast fallback for grid lines
    if contrast_ratio(palette.grid_major, palette.background) < 1.3:  # pragma: no cover
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
