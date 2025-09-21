"""Notification style guidelines (Milestone 0.20).

Defines a registry of standardized notification (toast / inline banner) styles.
Centralizing these prevents ad-hoc styling and enables consistent behavior for
stacking, auto-dismiss timing, and accessibility considerations.

Scope focuses on data-only semantic description; actual presentation (widgets,
animations, timers) will be implemented in later GUI layers.

Notification Model
------------------
Fields capture semantic concerns: severity, urgency, persistence, default
dismissal timeout, stacking priority, and recommended icon & color role tokens.

Design Considerations
---------------------
 - Pure dataclasses (test-friendly, decoupled from PyQt6).
 - Timeout of 0 => never auto-dismiss (requires user action).
 - `stacking_priority` lower number appears earlier in vertical stack.
 - `group_key` allows deduplication (e.g., repeated backend sync warnings).
 - `politeness` hints future ARIA / accessibility role (e.g., 'polite', 'assertive').
 - Strings remain English pending i18n extraction pass.

Future Extensions
-----------------
 - Add rate limiting metadata (max per minute).
 - Add telemetry code for analytics correlation.
 - Add action button descriptors (primary/secondary inline actions).
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, List, Optional

__all__ = [
    "NotificationStyle",
    "list_notification_styles",
    "get_notification_style",
]


@dataclass(frozen=True)
class NotificationStyle:
    """Semantic notification style definition.

    Attributes
    ----------
    id: str
        Stable style identifier (e.g., 'info', 'success').
    severity: str
        Logical severity bucket (info|success|warning|error|critical).
    icon: str
        Icon registry key.
    color_role: str
        Abstract color role token for background/accent usage.
    default_timeout_ms: int
        Auto-dismiss time in milliseconds (0 = persist until user closes).
    stacking_priority: int
        Lower values stack nearer to top (higher visibility).
    polite: bool
        If True, should announce non-interruptively; False may use assertive channel.
    group_key: Optional[str]
        Optional grouping key for deduplication / collapse logic.
    persistent: bool
        If True, treat as requiring explicit dismissal (timeout ignored if >0 vs external logic).
    """

    id: str
    severity: str
    icon: str
    color_role: str
    default_timeout_ms: int
    stacking_priority: int
    polite: bool
    group_key: Optional[str]
    persistent: bool


_REGISTRY: Dict[str, NotificationStyle] = {}


def _register(ns: NotificationStyle) -> None:
    if ns.id in _REGISTRY:
        raise ValueError(f"Duplicate notification style id: {ns.id}")
    _REGISTRY[ns.id] = ns


_register(
    NotificationStyle(
        id="info",
        severity="info",
        icon="status-info",
        color_role="alert-info",
        default_timeout_ms=5000,
        stacking_priority=50,
        polite=True,
        group_key=None,
        persistent=False,
    )
)
_register(
    NotificationStyle(
        id="success",
        severity="success",
        icon="status-success",
        color_role="alert-success",
        default_timeout_ms=4000,
        stacking_priority=40,
        polite=True,
        group_key=None,
        persistent=False,
    )
)
_register(
    NotificationStyle(
        id="warning",
        severity="warning",
        icon="status-warning",
        color_role="alert-warning",
        default_timeout_ms=0,  # stays until acknowledged to ensure awareness
        stacking_priority=30,
        polite=False,
        group_key="warnings",
        persistent=True,
    )
)
_register(
    NotificationStyle(
        id="error",
        severity="error",
        icon="status-error",
        color_role="alert-error",
        default_timeout_ms=0,
        stacking_priority=20,
        polite=False,
        group_key="errors",
        persistent=True,
    )
)
_register(
    NotificationStyle(
        id="critical",
        severity="critical",
        icon="status-critical",
        color_role="alert-critical",
        default_timeout_ms=0,
        stacking_priority=10,
        polite=False,
        group_key="critical",
        persistent=True,
    )
)


def list_notification_styles() -> List[NotificationStyle]:
    """Return styles sorted by ascending stacking_priority then id."""
    return sorted(_REGISTRY.values(), key=lambda n: (n.stacking_priority, n.id))


def get_notification_style(style_id: str) -> NotificationStyle:
    ns = _REGISTRY.get(style_id)
    if ns is None:
        raise KeyError(f"Unknown notification style id: {style_id}")
    return ns
