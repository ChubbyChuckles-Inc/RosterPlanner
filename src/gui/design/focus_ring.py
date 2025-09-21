"""Focus ring styling utilities (Milestone 0.31).

Defines a small struct + builder that produces a focus ring style configuration
with accessible contrast against an arbitrary background color while remaining
subtle. This is UI-framework agnostic; final QSS / painting translation will be
handled later.

Strategy:
- Accept primary outline color (desired) and fallback chain.
- Provide inner (solid) and outer (blurred) components with customizable widths.
- Validate hex colors (#RRGGBB or #AARRGGBB) and compute relative luminance.
- If contrast ratio against provided background < target (default 3.0), auto-pick
  a contrasting derived color (black or white) whichever yields higher ratio.

Contrast formula uses WCAG relative luminance algorithm (simplified, sRGB).
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Tuple
import re

__all__ = [
    "FocusRingStyle",
    "build_focus_ring_style",
    "contrast_ratio",
]

_HEX_RE = re.compile(r"^#(?:[0-9a-fA-F]{6}|[0-9a-fA-F]{8})$")


def _parse_hex(color: str) -> Tuple[int, int, int, int]:
    if not _HEX_RE.match(color):
        raise ValueError(f"Invalid hex color: {color}")
    color = color.lstrip("#")
    if len(color) == 6:
        r, g, b = color[0:2], color[2:4], color[4:6]
        a = "FF"
    else:
        a, r, g, b = color[0:2], color[2:4], color[4:6], color[6:8]
    return int(r, 16), int(g, 16), int(b, 16), int(a, 16)


def _channel_lum(raw: float) -> float:
    """Convert an sRGB channel (0-255) to linearized value for luminance.

    The previous implementation compared against an inflated threshold
    (0.03928 * 255) after normalizing, which incorrectly pushed most channels
    down the linear branch and depressed contrast ratios. This corrects the
    WCAG formula.
    """
    c = raw / 255.0
    if c <= 0.03928:
        return c / 12.92
    return ((c + 0.055) / 1.055) ** 2.4


def _relative_luminance(color: str) -> float:
    r, g, b, _ = _parse_hex(color)
    return 0.2126 * _channel_lum(r) + 0.7152 * _channel_lum(g) + 0.0722 * _channel_lum(b)


def contrast_ratio(fore: str, back: str) -> float:
    l1 = _relative_luminance(fore)
    l2 = _relative_luminance(back)
    lighter = max(l1, l2)
    darker = min(l1, l2)
    return (lighter + 0.05) / (darker + 0.05)


@dataclass(frozen=True)
class FocusRingStyle:
    primary_color: str
    inner_width_px: int
    outer_width_px: int
    outer_opacity: float
    effective_color: str  # possibly adjusted for contrast
    contrast_ratio: float

    def total_visual_width(self) -> int:
        return self.inner_width_px + self.outer_width_px


def _derive_contrasting(base: str, background: str) -> str:
    # Choose between pure white / black whichever is more contrasting.
    white = "#FFFFFF"
    black = "#000000"
    if contrast_ratio(white, background) >= contrast_ratio(black, background):
        return white
    return black


def build_focus_ring_style(
    *,
    desired_color: str,
    background_color: str,
    inner_width_px: int = 2,
    outer_width_px: int = 2,
    outer_opacity: float = 0.4,
    min_contrast: float = 3.0,
) -> FocusRingStyle:
    """Build focus ring style ensuring minimum contrast.

    Parameters
    ----------
    desired_color: The intended foreground outline hex.
    background_color: Background against which to test contrast.
    inner_width_px: Solid inner stroke width.
    outer_width_px: Soft glow/fade width.
    outer_opacity: 0..1 alpha for outer effect.
    min_contrast: Minimum acceptable contrast ratio.
    """
    # Validate numeric params.
    if inner_width_px < 1:
        raise ValueError("inner_width_px must be >= 1")
    if outer_width_px < 0:
        raise ValueError("outer_width_px must be >= 0")
    if not (0.0 <= outer_opacity <= 1.0):
        raise ValueError("outer_opacity must be between 0 and 1")

    # Validate colors / compute base contrast.
    _parse_hex(desired_color)
    _parse_hex(background_color)
    ratio = contrast_ratio(desired_color, background_color)
    effective = desired_color
    if ratio < min_contrast:
        effective = _derive_contrasting(desired_color, background_color)
        ratio = contrast_ratio(effective, background_color)

    return FocusRingStyle(
        primary_color=desired_color,
        inner_width_px=inner_width_px,
        outer_width_px=outer_width_px,
        outer_opacity=outer_opacity,
        effective_color=effective,
        contrast_ratio=round(ratio, 3),
    )
