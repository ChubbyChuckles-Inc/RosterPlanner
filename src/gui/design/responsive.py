"""Responsive breakpoints strategy (Milestone 0.21).

Even though the application targets desktop usage, users may resize the main
window to narrower widths (e.g., side-by-side multitasking). Establishing a
canonical breakpoint scale early prevents ad-hoc numeric checks scattered
through views and enables future adaptive behaviors (icon-only sidebars,
collapsed filter panels, etc.).

Design Goals
------------
 - Provide semantic breakpoint identifiers (xs, sm, md, lg, xl).
 - Centralize numeric pixel thresholds for reuse across layouts.
 - Offer helper to map a width to current breakpoint (stable & deterministic).
 - Allow future extension (e.g., xxl) without breaking existing logic.
 - Pure-Python, no Qt dependency for straightforward testing.

Breakpoint Scale (desktop-oriented conservative sizing):
 - xs: < 640px   (extremely narrow; collapse navigation to icons)
 - sm: >=640 & < 960px   (narrow; reduced paddings, stacked side panels)
 - md: >=960 & < 1280px  (baseline content layout)
 - lg: >=1280 & < 1600px (spacious; enable secondary sidebars)
 - xl: >=1600px          (wide; additional summary panels may appear)

Thresholds chosen align roughly with common web responsive ranges, adjusted
for desktop window scenarios. Width comparisons are inclusive on lower bound,
exclusive on upper bound except the final tier.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, List

__all__ = [
    "Breakpoint",
    "list_breakpoints",
    "get_breakpoint",
    "classify_width",
]


@dataclass(frozen=True)
class Breakpoint:
    """Semantic responsive breakpoint definition.

    Attributes
    ----------
    id: str
        Semantic identifier (xs|sm|md|lg|xl).
    min_width: int
        Inclusive lower pixel boundary.
    max_width: int
        Exclusive upper pixel boundary (None for open-ended final tier).
    description: str
        Guidance describing typical adaptive behaviors.
    """

    id: str
    min_width: int
    max_width: (
        int  # use -1 to denote None (Python 3.8 simple sentinel for immutability friendliness)
    )
    description: str

    def is_within(self, width: int) -> bool:
        upper = None if self.max_width == -1 else self.max_width
        if upper is None:
            return width >= self.min_width
        return self.min_width <= width < upper


_REGISTRY: Dict[str, Breakpoint] = {}


def _register(bp: Breakpoint) -> None:
    if bp.id in _REGISTRY:
        raise ValueError(f"Duplicate breakpoint id: {bp.id}")
    _REGISTRY[bp.id] = bp


_register(
    Breakpoint(
        id="xs",
        min_width=0,
        max_width=640,
        description="Ultra narrow window; hide text labels, icon-only navigation, single column.",
    )
)
_register(
    Breakpoint(
        id="sm",
        min_width=640,
        max_width=960,
        description="Narrow layout; collapse secondary side panels, reduce spacing scale.",
    )
)
_register(
    Breakpoint(
        id="md",
        min_width=960,
        max_width=1280,
        description="Default layout baseline; standard spacing and panel visibility.",
    )
)
_register(
    Breakpoint(
        id="lg",
        min_width=1280,
        max_width=1600,
        description="Spacious layout; enable auxiliary side panel or summary strip.",
    )
)
_register(
    Breakpoint(
        id="xl",
        min_width=1600,
        max_width=-1,  # open ended
        description="Wide layout; multi-column enhancements and persistent analytics panel.",
    )
)


def list_breakpoints() -> List[Breakpoint]:
    return sorted(_REGISTRY.values(), key=lambda b: b.min_width)


def get_breakpoint(bp_id: str) -> Breakpoint:
    bp = _REGISTRY.get(bp_id)
    if bp is None:
        raise KeyError(f"Unknown breakpoint id: {bp_id}")
    return bp


def classify_width(width: int) -> Breakpoint:
    """Return the Breakpoint matching the given width (pixels)."""
    if width < 0:
        raise ValueError("Width must be non-negative")
    for bp in list_breakpoints():
        if bp.is_within(width):
            return bp
    # Should not occur given xl is open-ended; defensive fallback
    return get_breakpoint("xl")
