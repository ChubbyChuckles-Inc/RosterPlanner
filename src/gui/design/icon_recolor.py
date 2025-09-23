"""Multi-tone icon recoloring pipeline (Milestone 5.10.30).

Provides a pure function for recoloring SVG markup that contains semantic
data-* attributes indicating tone layers. This supports mapping layered
vector icons onto theme token colors (primary / secondary / disabled).

Icon Markup Convention:
 <path data-tone="primary" fill="#000" ... />
 <path data-tone="secondary" fill="#111" ... />
 <path data-tone="accent" ... /> (future extension)

Only the ``fill`` attribute is manipulated (stroke left unchanged unless
we add explicit support later). If a path lacks a recognized data-tone it
is preserved verbatim.

Disabled State:
When ``state="disabled"`` the output colors are blended toward the surface
base color with an opacity reduction.

Design Tokens Dependence:
We reference theme tokens via a simple mapping parameter; caller resolves
theme tokens externally (keeps this module decoupled from theming loader
to improve testability). For convenience a helper `default_tone_map` can
be produced from loaded tokens at call sites.

Public API:
 - recolor_svg(svg: str, tone_colors: dict[str,str], state: str = "normal", surface_color: str | None = None) -> str
 - extract_tones(svg: str) -> set[str]

Test Coverage:
 - Recoloring primary & secondary layers.
 - Ignoring unknown tones.
 - Disabled state alpha reduction.
 - Idempotence when no tone attributes present.
"""

from __future__ import annotations

from typing import Dict, Set
import re

__all__ = ["recolor_svg", "extract_tones"]

TONE_ATTR_PATTERN = re.compile(r'data-tone\s*=\s*"([a-zA-Z0-9_-]+)"')
FILL_ATTR_PATTERN = re.compile(r'fill\s*=\s*"(#?[a-zA-Z0-9._()-]+)"')


def extract_tones(svg: str) -> Set[str]:
    return set(m.group(1) for m in TONE_ATTR_PATTERN.finditer(svg))


def _apply_disabled(color: str, surface: str | None) -> str:
    # Represent disabled by applying 50% alpha. If surface provided, we could blend.
    # For simplicity just append opacity via RGBA hex (#RRGGBBAA) when input is #RRGGBB.
    if not color.startswith("#") or len(color) not in {7, 9}:
        return color
    if len(color) == 9:  # already has alpha, reduce further
        base = color[:7]
    else:
        base = color
    return base + "80"  # 50% alpha


def recolor_svg(
    svg: str,
    tone_colors: Dict[str, str],
    *,
    state: str = "normal",
    surface_color: str | None = None,
) -> str:
    """Return recolored SVG markup.

    Parameters
    ----------
    svg: str
        Original SVG markup.
    tone_colors: dict[str,str]
        Mapping from tone name (e.g., 'primary', 'secondary', 'disabled') to
        hex color (#RRGGBB or #RRGGBBAA).
    state: str
        'normal' or 'disabled'. Disabled applies alpha reduction.
    surface_color: str | None
        Optional surface base color (future blending use).
    """
    # Quick scan: if no data-tone attributes, return early
    if "data-tone" not in svg:
        return svg

    def replace(match: re.Match) -> str:
        full = match.group(0)
        tone_match = TONE_ATTR_PATTERN.search(full)
        if not tone_match:
            return full
        tone = tone_match.group(1)
        color = tone_colors.get(tone)
        if color is None:
            return full  # unknown tone
        if state == "disabled":
            color = _apply_disabled(color, surface_color)
        # Replace or insert fill attribute
        if "fill=" in full:
            # Replace existing fill
            new_full = FILL_ATTR_PATTERN.sub(f'fill="{color}"', full)
        else:
            # Insert fill before closing
            new_full = full[:-1] + f' fill="{color}"' + full[-1]
        return new_full

    # Replace <path ...> segments individually
    path_pattern = re.compile(r"<path[^>]+>")
    return path_pattern.sub(replace, svg)
