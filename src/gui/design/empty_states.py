"""Empty state design templates (Milestone 0.18).

Central registry of semantic empty / placeholder states used across the UI.
Separating these definitions avoids ad-hoc strings and inconsistent UX.

Template Semantics:
 - id: stable key used by views (e.g., 'no-data', 'no-selection').
 - title: concise heading (user-visible, subject to i18n later).
 - message: explanatory text guiding next action.
 - primary_action_hint: suggested primary remediation (command label placeholder).
 - secondary_action_hint: optional alternative path.
 - icon: symbolic name referencing icon registry (placeholder if TBD).
 - severity: classification ('info', 'warning', 'error').

Design Choices:
 - Pure data; no GUI dependencies.
 - Intentionally English strings; future i18n pass will externalize.
 - Keep hints descriptive not imperative; actual action wiring occurs in view layer.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, List, Optional

__all__ = [
    "EmptyStateTemplate",
    "list_empty_states",
    "get_empty_state",
]


@dataclass(frozen=True)
class EmptyStateTemplate:
    id: str
    title: str
    message: str
    primary_action_hint: str
    secondary_action_hint: Optional[str]
    icon: str
    severity: str = "info"


_REGISTRY: Dict[str, EmptyStateTemplate] = {}


def _register(t: EmptyStateTemplate) -> None:
    if t.id in _REGISTRY:
        raise ValueError(f"Duplicate empty state id: {t.id}")
    _REGISTRY[t.id] = t


_register(
    EmptyStateTemplate(
        id="no-selection",
        title="Nothing Selected",
        message="Select a team, player, or division from the navigation panel to view details.",
        primary_action_hint="Browse navigation",
        secondary_action_hint=None,
        icon="placeholder-document",
        severity="info",
    )
)
_register(
    EmptyStateTemplate(
        id="no-data",
        title="No Data Loaded",
        message="No scraped data is available yet. Run a scrape to populate season data.",
        primary_action_hint="Run scrape",
        secondary_action_hint="Import snapshot",
        icon="placeholder-database",
        severity="info",
    )
)
_register(
    EmptyStateTemplate(
        id="search-empty",
        title="No Results",
        message="Your search did not match any teams or players. Adjust filters or keywords.",
        primary_action_hint="Refine search",
        secondary_action_hint="Clear filters",
        icon="placeholder-search",
        severity="info",
    )
)
_register(
    EmptyStateTemplate(
        id="error-generic",
        title="Something Went Wrong",
        message="An unexpected error occurred. Try again or check logs for details.",
        primary_action_hint="Retry action",
        secondary_action_hint="Open logs",
        icon="placeholder-error",
        severity="error",
    )
)


def list_empty_states() -> List[EmptyStateTemplate]:
    return sorted(_REGISTRY.values(), key=lambda t: t.id)


def get_empty_state(state_id: str) -> EmptyStateTemplate:
    t = _REGISTRY.get(state_id)
    if t is None:
        raise KeyError(f"Unknown empty state id: {state_id}")
    return t
