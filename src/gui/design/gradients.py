"""Gradient & tonal ramp registry (Milestone 5.10.21).

Provides a minimal in-memory registry for multi-stop gradients and tonal ramps
backed by design token colors. This is intentionally simple, focusing on
validation and discoverability; rendering adaptation (e.g., producing QSS or
QLinearGradient strings) can be layered later.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, List, Tuple, Iterable, Mapping

from .color_drift import normalize_hex

__all__ = [
    "GradientStop",
    "GradientDef",
    "register_gradient",
    "get_gradient",
    "list_gradients",
    "clear_gradients",
    "validate_gradient",
]


@dataclass(frozen=True)
class GradientStop:
    position: float  # 0.0 .. 1.0
    color: str  # #RRGGBB


@dataclass(frozen=True)
class GradientDef:
    id: str
    kind: str  # "linear" | "radial" | "tonal-ramp"
    stops: Tuple[GradientStop, ...]
    description: str | None = None


_REGISTRY: Dict[str, GradientDef] = {}


def register_gradient(gradient: GradientDef) -> None:
    validate_gradient(gradient)
    _REGISTRY[gradient.id] = gradient


def get_gradient(grad_id: str) -> GradientDef:
    return _REGISTRY[grad_id]


def list_gradients() -> List[GradientDef]:  # noqa: D401
    return list(_REGISTRY.values())


def clear_gradients() -> None:  # noqa: D401
    _REGISTRY.clear()


def validate_gradient(gradient: GradientDef) -> None:
    if not gradient.id or any(ch.isspace() for ch in gradient.id):
        raise ValueError("Gradient id must be non-empty and contain no whitespace")
    if gradient.kind not in {"linear", "radial", "tonal-ramp"}:
        raise ValueError("Unsupported gradient kind")
    if len(gradient.stops) < 2:
        raise ValueError("Gradient must have at least two stops")
    last_pos = -1.0
    for stop in gradient.stops:
        if not (0.0 <= stop.position <= 1.0):
            raise ValueError("Stop position out of range [0,1]")
        if stop.position < last_pos:
            raise ValueError("Stop positions must be non-decreasing")
        last_pos = stop.position
        c = normalize_hex(stop.color)
        if len(c) != 7:
            raise ValueError("Color must normalize to #RRGGBB")


# Default gradients ----------------------------------------------------
def _ensure_defaults() -> None:
    if _REGISTRY:
        return
    register_gradient(
        GradientDef(
            id="accent-ramp",
            kind="tonal-ramp",
            stops=(
                GradientStop(0.0, "#0A3368"),
                GradientStop(0.25, "#144C99"),
                GradientStop(0.5, "#1E63C9"),
                GradientStop(0.75, "#2E7DEB"),
                GradientStop(1.0, "#4C8DFF"),
            ),
            description="Primary accent tonal ramp (dark->light)",
        )
    )
    register_gradient(
        GradientDef(
            id="background-elevation",
            kind="linear",
            stops=(
                GradientStop(0.0, "#0E1116"),
                GradientStop(1.0, "#1C232B"),
            ),
            description="Subtle vertical dark elevation blend",
        )
    )
    register_gradient(
        GradientDef(
            id="status-positive-ramp",
            kind="tonal-ramp",
            stops=(
                GradientStop(0.0, "#0F3A17"),
                GradientStop(0.5, "#1F6A2D"),
                GradientStop(1.0, "#3FA55B"),
            ),
            description="Green success ramp",
        )
    )


_ensure_defaults()
