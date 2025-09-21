"""Micro-interaction catalog (Milestone 0.15).

Defines a lightweight, data-driven registry of standard interaction visual
semantics used across components (hover, press, selection, drag indicators).

Goals:
 - Centralize micro-interaction design tokens separate from core color tokens.
 - Provide consistent durations and easing references (re-using motion tokens).
 - Remain framework-agnostic (no PyQt imports) for easy unit testing.

Each micro interaction describes semantic intent + recommended styling hints.
Actual rendering (e.g., applying QPropertyAnimation or updating QSS classes)
will occur in downstream view helpers; this catalog avoids any runtime side
effects and serves as a single source of truth.

Design choices:
 - Use simple dataclass `MicroInteraction` with optional numeric intensity for
   states that may scale (e.g., press vs long press variant future expansion).
 - Provide registry accessor functions: `list_micro_interactions`, `get_micro_interaction`.
 - Keep styling hints descriptive, not imperative (e.g., 'raise elevation by 1').
 - Defer platform/Qt specifics to later integration tasks to preserve decoupling.

Future Extensions:
 - Add reduced motion alternatives.
 - Add haptic feedback hints (for potential cross-platform abstraction or future touch devices).
 - Add analytics hooks to measure dwell time or activation latency.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, List

__all__ = [
    "MicroInteraction",
    "get_micro_interaction",
    "list_micro_interactions",
]


@dataclass(frozen=True)
class MicroInteraction:
    """Describes a semantic UI micro-interaction.

    Attributes
    ----------
    name: str
        Identifier key (e.g., 'hover', 'press').
    description: str
        Human-readable description of the intent.
    styling_hints: list[str]
        Declarative hints; consumer maps these to concrete visuals (e.g., QSS class changes).
    duration_token: str
        Reference into motion duration tokens (e.g., 'subtle', 'instant').
    easing_token: str
        Reference into motion easing tokens (e.g., 'standard', 'decelerate').
    intensity: int
        Relative weight (1=baseline). Reserved for future differentiation.
    """

    name: str
    description: str
    styling_hints: List[str]
    duration_token: str
    easing_token: str
    intensity: int = 1


# Registry -----------------------------------------------------------------
_REGISTRY: Dict[str, MicroInteraction] = {}


def _register(mi: MicroInteraction) -> None:
    if mi.name in _REGISTRY:
        raise ValueError(f"MicroInteraction already registered: {mi.name}")
    _REGISTRY[mi.name] = mi


# Seed default catalog (stable order not guaranteed by dict; list accessor sorts)
_register(
    MicroInteraction(
        name="hover",
        description="Pointer hovers over actionable element (non-touch).",
        styling_hints=["slight background tint", "increase elevation by 1", "cursor: pointer"],
        duration_token="instant",
        easing_token="standard",
    )
)
_register(
    MicroInteraction(
        name="press",
        description="Immediate press/click feedback indicating activation.",
        styling_hints=["decrease elevation by 1 (or invert)", "compress scale to 0.97"],
        duration_token="instant",
        easing_token="standard",
    )
)
_register(
    MicroInteraction(
        name="selection",
        description="Element becomes part of a persistent selection set.",
        styling_hints=["outline focus ring", "accent background fill 8% alpha"],
        duration_token="subtle",
        easing_token="standard",
    )
)
_register(
    MicroInteraction(
        name="drag-start",
        description="User begins dragging an element (mouse down + move threshold met).",
        styling_hints=["raise elevation by 2", "apply shadow accent tint", "cursor: grabbing"],
        duration_token="subtle",
        easing_token="accelerate",
    )
)
_register(
    MicroInteraction(
        name="drag-over",
        description="Dragged element hovers over a valid drop target.",
        styling_hints=["pulse border accent", "highlight drop zone background"],
        duration_token="subtle",
        easing_token="standard",
    )
)
_register(
    MicroInteraction(
        name="drop",
        description="Successful drop completes drag interaction.",
        styling_hints=["flash success tint", "settle elevation to normal"],
        duration_token="pronounced",
        easing_token="decelerate",
    )
)


# Public API ---------------------------------------------------------------


def list_micro_interactions() -> List[MicroInteraction]:
    """Return catalog as a list sorted by name for deterministic iteration."""
    return sorted(_REGISTRY.values(), key=lambda m: m.name)


def get_micro_interaction(name: str) -> MicroInteraction:
    """Lookup a micro interaction by name.

    Raises
    ------
    KeyError
        If the name is not registered.
    """
    mi = _REGISTRY.get(name)
    if mi is None:
        raise KeyError(f"Unknown micro interaction: {name}")
    return mi
