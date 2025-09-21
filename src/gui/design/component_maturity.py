"""Component maturity index (Milestone 0.49).

Provides a lightweight registry to track the stability level of UI components
within the design system / GUI layer. This enables downstream tooling (docs,
gallery badges, warnings) and informs consumers about expected API stability.

Statuses
--------
 - alpha: Experimental; API and visuals may change without notice.
 - beta: Functionally complete; minor breaking changes still possible.
 - stable: API/visuals frozen except for backward-compatible additions.

Features
--------
 - Dataclass `ComponentMaturity` capturing id, status, description, risks, since_version.
 - Registry with duplicate id protection.
 - Summary helper aggregating counts by status.
 - Validation of allowed statuses.
 - Clear/reset for tests.

Future Enhancements (Not in scope now)
-------------------------------------
 - Deprecation tracking (date, replacement)
 - Semantic version impact analysis
 - Export to documentation site generator
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, List, Tuple

__all__ = [
    "ComponentMaturity",
    "register_component_maturity",
    "get_component_maturity",
    "list_component_maturity",
    "clear_component_maturity",
    "summarize_maturity",
]

ALLOWED_STATUSES = {"alpha", "beta", "stable"}


@dataclass(frozen=True)
class ComponentMaturity:
    component_id: str
    status: str  # one of ALLOWED_STATUSES
    description: str
    risks: str = ""
    since_version: str = "0.0.0"

    def badge_label(self) -> str:  # pragma: no cover trivial formatting
        return f"{self.status.upper()}"


_REGISTRY: Dict[str, ComponentMaturity] = {}


def register_component_maturity(entry: ComponentMaturity) -> None:
    if entry.status not in ALLOWED_STATUSES:
        raise ValueError(f"Invalid status '{entry.status}' (allowed: {sorted(ALLOWED_STATUSES)})")
    if entry.component_id in _REGISTRY:
        raise ValueError(f"Duplicate component id '{entry.component_id}'")
    _REGISTRY[entry.component_id] = entry


def get_component_maturity(component_id: str) -> ComponentMaturity:
    return _REGISTRY[component_id]


def list_component_maturity() -> List[ComponentMaturity]:
    return list(_REGISTRY.values())


def clear_component_maturity() -> None:
    _REGISTRY.clear()


def summarize_maturity() -> Dict[str, int]:
    summary: Dict[str, int] = {s: 0 for s in ALLOWED_STATUSES}
    for entry in _REGISTRY.values():
        summary[entry.status] = summary.get(entry.status, 0) + 1
    return summary
