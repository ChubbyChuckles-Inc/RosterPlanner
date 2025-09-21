"""EventBus core (Milestone 1.5).

Lightweight synchronous publish/subscribe mechanism with typed events.

Goals:
 - Decouple producers and consumers inside the GUI layer
 - Provide minimal, testable surface (no Qt dependency)
 - Safe error isolation: one failing handler doesn't break the publish cycle
 - Allow one-shot (once) subscriptions
 - Provide unsubscribe handles

Non-goals (deferred to Milestone 1.5.1):
 - Tracing ring buffer
 - Toggleable global tracing
 - Async / threaded dispatch
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from threading import RLock
from time import perf_counter
from typing import Any, Dict, List, Protocol, Deque, Tuple
from collections import deque

__all__ = [
    "GUIEvent",
    "Event",
    "EventBus",
    "EventHandler",
    "Subscription",
    "TraceEntry",
]


class GUIEvent(str, Enum):  # Using str subclass for easier JSON/UI usage
    STARTUP_COMPLETE = "startup_complete"
    THEME_CHANGED = "theme_changed"
    DATA_REFRESH_REQUESTED = "data_refresh_requested"
    DATA_REFRESH_COMPLETED = "data_refresh_completed"
    ERROR_OCCURRED = "error_occurred"
    DATA_REFRESHED = "data_refreshed"  # aggregated signal post-refresh pipeline
    SELECTION_CHANGED = "selection_changed"
    STATS_UPDATED = "stats_updated"


@dataclass
class Event:
    name: str  # matches GUIEvent value or custom string
    payload: Any
    timestamp: float


class EventHandler(Protocol):  # noqa: D401 - protocol signature docs implicit
    def __call__(self, event: Event) -> None: ...  # pragma: no cover - structural


@dataclass
class Subscription:
    event: str
    handler: EventHandler
    once: bool
    active: bool = True

    def cancel(self) -> None:
        self.active = False


@dataclass(frozen=True)
class TraceEntry:
    name: str
    timestamp: float
    summary: str


class EventBus:
    """Synchronous event dispatcher with optional tracing.

    Thread-safety: subscription list and tracing structures are guarded by a
    re-entrant lock. Handlers are invoked while the lock is NOT held
    (copy-first strategy) so handlers can subscribe/unsubscribe recursively
    without deadlock.

    Tracing (Milestone 1.5.1):
        - Disabled by default
        - When enabled, stores a fixed-size ring buffer (default 50) of recent
          events (name, timestamp, short payload summary)
        - Tracing is lightweight: only captures a small tuple for each event
    """

    DEFAULT_TRACE_CAPACITY = 50

    def __init__(self) -> None:
        self._lock = RLock()
        self._subs: Dict[str, List[Subscription]] = {}
        self._errors: List[tuple[Event, BaseException]] = []
        # Tracing state
        self._tracing_enabled: bool = False
        self._trace_capacity: int = self.DEFAULT_TRACE_CAPACITY
        self._traces: Deque[Tuple[str, float, str]] = deque(maxlen=self._trace_capacity)

    # ------------------------------------------------------------------
    # Subscription management
    # ------------------------------------------------------------------
    def subscribe(
        self, name: str | GUIEvent, handler: EventHandler, *, once: bool = False
    ) -> Subscription:
        key = name.value if isinstance(name, GUIEvent) else name
        sub = Subscription(event=key, handler=handler, once=once)
        with self._lock:
            self._subs.setdefault(key, []).append(sub)
        return sub

    def unsubscribe(self, sub: Subscription) -> None:
        with self._lock:
            bucket = self._subs.get(sub.event)
            if not bucket:
                return
            for i, existing in enumerate(bucket):
                if existing is sub:
                    bucket.pop(i)
                    break
            if not bucket:
                self._subs.pop(sub.event, None)
        sub.active = False

    def clear(self) -> None:
        with self._lock:
            self._subs.clear()
            self._errors.clear()

    # ------------------------------------------------------------------
    # Publishing
    # ------------------------------------------------------------------
    def publish(self, name: str | GUIEvent, payload: Any = None) -> Event:
        key = name.value if isinstance(name, GUIEvent) else name
        evt = Event(name=key, payload=payload, timestamp=perf_counter())
        # Snapshot subscribers first
        with self._lock:
            subs = list(self._subs.get(key, ()))
            tracing = self._tracing_enabled
        # Lightweight trace capture (done outside lock except ring append)
        if tracing:
            summary: str
            if payload is None:
                summary = "-"
            else:
                # Keep summary concise; fall back to type name.
                text = str(payload)
                summary = text if len(text) <= 40 else text[:37] + "..."
            with self._lock:
                self._traces.append((evt.name, evt.timestamp, summary))
        # Dispatch without holding the lock
        to_remove: List[Subscription] = []
        for sub in subs:
            if not sub.active:
                continue
            try:
                sub.handler(evt)
            except BaseException as exc:  # noqa: BLE001 - capture any handler failure
                self._errors.append((evt, exc))
            else:
                if sub.once:
                    to_remove.append(sub)
        # Post-cleanup (remove once-handlers)
        if to_remove:
            with self._lock:
                bucket = self._subs.get(key)
                if bucket:
                    self._subs[key] = [s for s in bucket if s not in to_remove]
                    if not self._subs[key]:
                        self._subs.pop(key, None)
        return evt

    # ------------------------------------------------------------------
    # Introspection
    # ------------------------------------------------------------------
    def subscriber_count(self, name: str | GUIEvent) -> int:
        key = name.value if isinstance(name, GUIEvent) else name
        with self._lock:
            return len(self._subs.get(key, ()))

    def list_events(self) -> list[str]:
        with self._lock:
            return list(self._subs.keys())

    @property
    def errors(self) -> list[tuple[Event, BaseException]]:
        with self._lock:
            return list(self._errors)

    # ------------------------------------------------------------------
    # Tracing API
    # ------------------------------------------------------------------
    def enable_tracing(self, enabled: bool = True, *, capacity: int | None = None) -> None:
        """Enable or disable event tracing.

        Parameters
        ----------
        enabled: bool
            New tracing state.
        capacity: int | None
            Optional new ring buffer capacity (resets existing traces if changed).
        """
        with self._lock:
            self._tracing_enabled = enabled
            if capacity is not None and capacity != self._trace_capacity:
                self._trace_capacity = capacity
                self._traces = deque(self._traces, maxlen=capacity)

    def clear_traces(self) -> None:
        with self._lock:
            self._traces.clear()

    def recent_traces(self) -> list[Tuple[str, float, str]]:
        with self._lock:
            return list(self._traces)

    def recent_trace_entries(self) -> list[TraceEntry]:
        with self._lock:
            return [TraceEntry(name=n, timestamp=ts, summary=s) for (n, ts, s) in self._traces]

    @property
    def tracing_enabled(self) -> bool:
        with self._lock:
            return self._tracing_enabled
