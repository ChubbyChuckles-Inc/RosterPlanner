"""Onboarding tour framework placeholder (Milestone 0.30).

Provides a registry-based definition model for progressively educative tours.
Actual UI overlay / step highlighting will be added in future milestones; this
module focuses on data modeling & retrieval logic (testable headless).
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Dict, List, Optional, Sequence

__all__ = [
    "TourStep",
    "TourDefinition",
    "register_tour",
    "get_tour",
    "list_tours",
    "clear_tours",
]


@dataclass(frozen=True)
class TourStep:
    id: str
    title: str
    body: str
    anchor_id: Optional[str] = None  # UI element identifier (future mapping)
    next_id: Optional[str] = None


@dataclass(frozen=True)
class TourDefinition:
    id: str
    steps: Sequence[TourStep] = field(default_factory=list)
    version: int = 1
    description: str = ""

    def step_ids(self) -> List[str]:  # convenience
        return [s.id for s in self.steps]


_registry: Dict[str, TourDefinition] = {}


def register_tour(defn: TourDefinition) -> None:
    if defn.id in _registry:
        raise ValueError(f"Tour already registered: {defn.id}")
    # basic validation: unique step IDs
    ids = set()
    for step in defn.steps:
        if step.id in ids:
            raise ValueError(f"Duplicate step id {step.id} in tour {defn.id}")
        ids.add(step.id)
    _registry[defn.id] = defn


def get_tour(tour_id: str) -> TourDefinition:
    return _registry[tour_id]


def list_tours() -> List[TourDefinition]:
    return list(_registry.values())


def clear_tours() -> None:
    _registry.clear()
