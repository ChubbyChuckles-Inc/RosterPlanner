"""Service layer exports.

Responsibilities:
 - Dependency/service locator (`services`)
 - EventBus publish/subscribe core

Stability:
 - `ServiceLocator` and `EventBus` are considered beta (API may grow but existing
     methods will not break without deprecation cycle).
 - Keys for services are string-based; may move to Protocol-based lookups later.
"""

from .service_locator import services, ServiceLocator  # noqa: F401
from .event_bus import EventBus, GUIEvent  # noqa: F401

__all__ = [
    "services",
    "ServiceLocator",
    "EventBus",
    "GUIEvent",
]
