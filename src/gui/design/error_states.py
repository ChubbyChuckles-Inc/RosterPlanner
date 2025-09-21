"""Error state visual taxonomy (Milestone 0.19).

Provides a centralized registry describing semantic tiers of error / problem
feedback in the UI. This decouples presentation logic from ad-hoc severity
strings and ensures future consistency across dialogs, inline banners, status
chips, and notification toasts.

Severity Model
--------------
Three canonical tiers are defined initially (can be extended in future):
 - soft-warning: Non-blocking issue or degraded state. User can often proceed.
 - blocking-error: Operation failed; user action required before proceeding.
 - critical-failure: System/major subsystem unusable; escalation warranted.

Each entry encodes recommended icon, color role tokens (abstract names; actual
mapping occurs in theming layer), default user action guidance, and escalation
policy notes consumed by logging / telemetry surfaces.

Design Choices
--------------
 - Pure data objects (no Qt dependencies) for testability.
 - Field names intentionally explicit to aid future ADR / docs generation.
 - Color roles are symbolic; final palette resolution happens in theme layer.
 - Escalation guidance kept concise; richer playbooks can link by id later.
 - Keep strings English until broader i18n externalization pass.

Future Extensions
-----------------
 - Add `telemetry_code` for analytics correlation.
 - Add `recommended_aria_role` for accessibility annotation helpers.
 - Add `cooldown_seconds` for suppression heuristics.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, List

__all__ = [
    "ErrorState",
    "list_error_states",
    "get_error_state",
]


@dataclass(frozen=True)
class ErrorState:
    """Describes a semantic error/problem severity tier.

    Attributes
    ----------
    id: str
        Stable identifier key (e.g., 'soft-warning').
    level: int
        Numeric ordering (ascending severity). Guarantees deterministic sorting.
    label: str
        Short human-readable label (UI heading / badge text baseline).
    description: str
        Expanded explanation for tooltips or inline help.
    icon: str
        Icon registry symbolic name (placeholder naming until icon set finalized).
    color_role: str
        Abstract color token role (e.g., 'alert-warning', 'alert-error').
    recommended_action: str
        Primary remediation guidance for user.
    escalation: str
        Guidance on logging / surfacing (e.g., 'log warning', 'log error & prompt feedback').
    persistent: bool
        Whether UI element should persist until dismissed (True) or can auto-fade.
    blocking: bool
        Indicates if flow should be halted until resolved.
    """

    id: str
    level: int
    label: str
    description: str
    icon: str
    color_role: str
    recommended_action: str
    escalation: str
    persistent: bool
    blocking: bool


_REGISTRY: Dict[str, ErrorState] = {}


def _register(es: ErrorState) -> None:
    if es.id in _REGISTRY:
        raise ValueError(f"Duplicate error state id: {es.id}")
    _REGISTRY[es.id] = es


_register(
    ErrorState(
        id="soft-warning",
        level=10,
        label="Warning",
        description="Minor issue or degraded capability. User may proceed with caution.",
        icon="status-warning",
        color_role="alert-warning",
        recommended_action="Review details and optionally adjust",
        escalation="log warning",
        persistent=False,
        blocking=False,
    )
)
_register(
    ErrorState(
        id="blocking-error",
        level=20,
        label="Error",
        description="Operation failed and cannot complete without user intervention.",
        icon="status-error",
        color_role="alert-error",
        recommended_action="Resolve issue then retry",
        escalation="log error & show dialog",
        persistent=True,
        blocking=True,
    )
)
_register(
    ErrorState(
        id="critical-failure",
        level=30,
        label="Critical Failure",
        description="Severe failure impacting core functionality or data integrity.",
        icon="status-critical",
        color_role="alert-critical",
        recommended_action="Collect logs and restart application",
        escalation="log critical & prompt feedback",
        persistent=True,
        blocking=True,
    )
)


def list_error_states() -> List[ErrorState]:
    """Return error states sorted by ascending severity level then id."""
    return sorted(_REGISTRY.values(), key=lambda e: (e.level, e.id))


def get_error_state(state_id: str) -> ErrorState:
    es = _REGISTRY.get(state_id)
    if es is None:
        raise KeyError(f"Unknown error state id: {state_id}")
    return es
