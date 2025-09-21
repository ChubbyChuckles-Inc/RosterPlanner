"""Progressive enhancement ladder utilities (Milestone 0.40).

Defines a small framework to describe capability tiers and conditionally
activate enhancement features beyond the baseline. This allows the GUI to
run in a minimal, universally compatible mode while opportunistically
layering richer interactions or visuals when environment predicates pass
(e.g., GPU acceleration, high-DPI correctness, available memory, theme
support readiness).

Design:
- EnhancementTier: dataclass capturing id, description, ordering weight.
- EnhancementFeature: dataclass capturing id, tier_id, description, and an
  activation predicate callable returning bool.
- Registry for tiers & features with duplicate prevention.
- Activation evaluation returning an ordered list of active features.
- Pure logic; integration layer can supply predicates for real system checks.

Public API:
- register_tier(tier: EnhancementTier)
- list_tiers() -> list[EnhancementTier] (sorted by weight asc)
- get_tier(id: str) -> EnhancementTier | None
- register_feature(feature: EnhancementFeature)
- list_features() -> list[EnhancementFeature]
- evaluate_active_features(context: dict | None = None) -> list[EnhancementFeature]
- clear_enhancement_registry()
- ensure_default_tiers() -> int

Default Tiers (ascending enrichment):
- baseline: Minimal guaranteed functionality
- extended: Additional non-critical polish (e.g., subtle animations)
- enhanced: Higher-level UX augmentation (e.g., live previews)
- deluxe: Advanced / GPU-intensive or experimental features

Testing Focus:
- Idempotent default tier loading
- Feature predicate gating
- Ordering by tier weight then feature id
- Duplicate id prevention for tiers and features

Python 3.8 compatible.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Callable, Dict, List, Optional, Tuple

__all__ = [
    "EnhancementTier",
    "EnhancementFeature",
    "register_tier",
    "list_tiers",
    "get_tier",
    "register_feature",
    "list_features",
    "evaluate_active_features",
    "clear_enhancement_registry",
    "ensure_default_tiers",
]

Predicate = Callable[[Optional[dict]], bool]


@dataclass(frozen=True)
class EnhancementTier:
    id: str
    description: str
    weight: int  # lower first

    def __post_init__(self):  # type: ignore[override]
        if not self.id.strip():
            raise ValueError("tier id must be non-empty")
        if not self.description.strip():
            raise ValueError("tier description must be non-empty")
        if self.weight < 0:
            raise ValueError("tier weight must be >= 0")


@dataclass(frozen=True)
class EnhancementFeature:
    id: str
    tier_id: str
    description: str
    predicate: Predicate

    def __post_init__(self):  # type: ignore[override]
        if not self.id.strip():
            raise ValueError("feature id must be non-empty")
        if not self.tier_id.strip():
            raise ValueError("feature tier_id must be non-empty")
        if not self.description.strip():
            raise ValueError("feature description must be non-empty")
        if not callable(self.predicate):
            raise ValueError("predicate must be callable")


_tiers: Dict[str, EnhancementTier] = {}
_features: Dict[str, EnhancementFeature] = {}


def register_tier(tier: EnhancementTier) -> None:
    if tier.id in _tiers:
        raise ValueError(f"tier '{tier.id}' already registered")
    _tiers[tier.id] = tier


def list_tiers() -> List[EnhancementTier]:
    return sorted(_tiers.values(), key=lambda t: (t.weight, t.id))


def get_tier(tier_id: str) -> Optional[EnhancementTier]:
    return _tiers.get(tier_id)


def register_feature(feature: EnhancementFeature) -> None:
    if feature.id in _features:
        raise ValueError(f"feature '{feature.id}' already registered")
    if feature.tier_id not in _tiers:
        raise ValueError(f"tier '{feature.tier_id}' not registered for feature '{feature.id}'")
    _features[feature.id] = feature


def list_features() -> List[EnhancementFeature]:
    # stable ordering: tier weight then feature id
    return sorted(
        _features.values(),
        key=lambda f: (get_tier(f.tier_id).weight if get_tier(f.tier_id) else 9999, f.id),
    )


def evaluate_active_features(context: Optional[dict] = None) -> List[EnhancementFeature]:
    active: List[EnhancementFeature] = []
    for f in list_features():
        try:
            if f.predicate(context):
                active.append(f)
        except Exception:
            # Fail closed: if predicate errors treat as inactive
            continue
    return active


def clear_enhancement_registry() -> None:
    _tiers.clear()
    _features.clear()


_DEFAULT_TIERS = [
    EnhancementTier("baseline", "Minimal guaranteed functionality", 0),
    EnhancementTier("extended", "Additional non-critical polish", 10),
    EnhancementTier("enhanced", "Higher-level UX augmentation", 20),
    EnhancementTier("deluxe", "Advanced or experimental features", 30),
]


def ensure_default_tiers() -> int:
    added = 0
    for t in _DEFAULT_TIERS:
        if t.id not in _tiers:
            _tiers[t.id] = t
            added += 1
    return added
