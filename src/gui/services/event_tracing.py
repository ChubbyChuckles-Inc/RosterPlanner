"""Event tracing convenience API (Milestone 1.5.1).

Provides a thin abstraction around `EventBus` tracing so callers don't need to
import the bus directly for common diagnostic operations.
"""

from __future__ import annotations

from typing import Iterable
from .event_bus import EventBus, TraceEntry
from .service_locator import services

__all__ = [
    "enable_event_tracing",
    "disable_event_tracing",
    "get_recent_event_traces",
]


def _bus() -> EventBus:
    return services.get_typed("event_bus", EventBus)


def enable_event_tracing(*, capacity: int | None = None) -> None:
    bus = _bus()
    bus.enable_tracing(True, capacity=capacity)


def disable_event_tracing() -> None:
    _bus().enable_tracing(False)


def get_recent_event_traces() -> list[TraceEntry]:
    return _bus().recent_trace_entries()
