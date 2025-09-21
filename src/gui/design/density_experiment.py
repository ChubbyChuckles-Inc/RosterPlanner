"""Visual density A/B toggling harness (Milestone 0.34).

Provides a headless, testable mechanism to switch between density variants
(e.g., comfortable, compact) plus an experimental 'cozy' or 'ultra-compact'
slot for future UX experimentation. Tracks history and notifies registered
listeners of variant changes (for eventual UI relayout triggers).
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import List, Callable, Sequence, Dict
import time

__all__ = [
    "DensityExperimentState",
    "set_density_variant",
    "current_density_variant",
    "list_density_variants",
    "register_density_listener",
    "density_history",
    "clear_density_state",
]

# Canonical baseline variants (align with density_manager naming where possible)
_VARIANTS: List[str] = ["comfortable", "compact", "cozy"]
_DEFAULT = "comfortable"
_MAX_HISTORY = 50


@dataclass(frozen=True)
class DensityExperimentState:
    variant: str
    timestamp: float


_state: DensityExperimentState = DensityExperimentState(_DEFAULT, time.time())
_history: List[DensityExperimentState] = [_state]
_listeners: List[Callable[[DensityExperimentState], None]] = []
_metrics: Dict[str, int] = {"switch_count": 0, "suppressed": 0}


def list_density_variants() -> Sequence[str]:
    return list(_VARIANTS)


def current_density_variant() -> str:
    return _state.variant


def density_history() -> Sequence[DensityExperimentState]:
    return list(_history)


def register_density_listener(cb: Callable[[DensityExperimentState], None]) -> None:
    if cb not in _listeners:
        _listeners.append(cb)


def set_density_variant(variant: str) -> DensityExperimentState:
    global _state
    if variant not in _VARIANTS:
        raise ValueError(f"Unknown density variant: {variant}")
    if variant == _state.variant:
        _metrics["suppressed"] += 1
        return _state
    _state = DensityExperimentState(variant=variant, timestamp=time.time())
    _history.append(_state)
    if len(_history) > _MAX_HISTORY:
        del _history[0 : len(_history) - _MAX_HISTORY]
    _metrics["switch_count"] += 1
    for cb in list(_listeners):  # snapshot list to avoid mutation issues
        try:
            cb(_state)
        except Exception:  # noqa: BLE001 - listeners should not break flow
            continue
    return _state


def clear_density_state() -> None:
    global _state
    _listeners.clear()
    _history.clear()
    _state = DensityExperimentState(_DEFAULT, time.time())
    _history.append(_state)
    _metrics.update({"switch_count": 0, "suppressed": 0})
