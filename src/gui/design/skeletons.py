"""Skeleton loader variants (Milestone 0.17).

Provides semantic placeholder variants for loading states (table rows, cards,
charts). These are data descriptors only; actual painting / widgets will be
implemented later. Centralizing structure ensures consistency and testability.

Design Goals:
 - Keep representation lightweight & declarative (no Qt imports).
 - Reference motion duration/easing tokens for shimmer or fade loops.
 - Allow future extensions (e.g., adjustable density, dark/light adaptation).

Variant Semantics:
 - table-row: Horizontal band with optional avatar circle + multiple rectangular blocks.
 - card: Rounded rectangle with title line, subtitle line, content block area.
 - chart-placeholder: Simple grid + bar/line zone placeholders.

Each variant provides ordered shape descriptors for a hypothetical layout.
Shapes use a very small schema to avoid over-engineering at this stage.

Schema for shapes:
 { "type": "rect" | "circle", "w": int, "h": int, "radius": int (optional), "style": str (semantic subrole) }

This affords later mapping to actual painted geometry or QML-like constructs.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, List

__all__ = [
    "SkeletonVariant",
    "list_skeleton_variants",
    "get_skeleton_variant",
]


@dataclass(frozen=True)
class SkeletonVariant:
    """Describes a skeleton loader variant.

    Attributes
    ----------
    name: str
        Identifier (e.g., 'table-row').
    shapes: list[dict]
        Ordered placeholder shape specs (see module doc). Dimensions are nominal units.
    duration_token: str
        Motion duration token controlling shimmer/fade cycle.
    easing_token: str
        Motion easing token for transitions.
    notes: str
        Optional rationale or usage guidance.
    """

    name: str
    shapes: List[Dict[str, object]]
    duration_token: str
    easing_token: str
    notes: str = ""


_REGISTRY: Dict[str, SkeletonVariant] = {}


def _register(v: SkeletonVariant) -> None:
    if v.name in _REGISTRY:
        raise ValueError(f"Duplicate skeleton variant: {v.name}")
    _REGISTRY[v.name] = v


_register(
    SkeletonVariant(
        name="table-row",
        shapes=[
            {"type": "circle", "w": 16, "h": 16, "style": "avatar"},
            {"type": "rect", "w": 120, "h": 10, "radius": 3, "style": "primary"},
            {"type": "rect", "w": 80, "h": 10, "radius": 3, "style": "secondary"},
            {"type": "rect", "w": 40, "h": 10, "radius": 3, "style": "meta"},
        ],
        duration_token="subtle",
        easing_token="standard",
        notes="Represents a single data row with avatar and three columns",
    )
)

_register(
    SkeletonVariant(
        name="card",
        shapes=[
            {"type": "rect", "w": 160, "h": 12, "radius": 4, "style": "title"},
            {"type": "rect", "w": 110, "h": 10, "radius": 4, "style": "subtitle"},
            {"type": "rect", "w": 200, "h": 90, "radius": 6, "style": "content"},
        ],
        duration_token="subtle",
        easing_token="standard",
        notes="Generic card layout placeholder",
    )
)

_register(
    SkeletonVariant(
        name="chart-placeholder",
        shapes=[
            {"type": "rect", "w": 220, "h": 100, "radius": 4, "style": "plot-area"},
            {"type": "rect", "w": 60, "h": 10, "radius": 3, "style": "legend-line"},
            {"type": "rect", "w": 50, "h": 10, "radius": 3, "style": "legend-line"},
        ],
        duration_token="pronounced",
        easing_token="decelerate",
        notes="Simplified chart canvas with legend items",
    )
)


def list_skeleton_variants() -> List[SkeletonVariant]:
    return sorted(_REGISTRY.values(), key=lambda v: v.name)


def get_skeleton_variant(name: str) -> SkeletonVariant:
    v = _REGISTRY.get(name)
    if v is None:
        raise KeyError(f"Unknown skeleton variant: {name}")
    return v
