"""Focus Trail Service (Milestone 5.10.40).

Captures a short trail of recently focused widgets driven by keyboard navigation
and exposes a pure function interface for computing the ordered trail suitable
for a lightweight highlight overlay (future enhancement).

Principles:
 - Separation of concerns: service owns ONLY data (recent focus ids + timestamps).
 - No direct styling here: views or a future overlay can subscribe to event_bus.
 - Testability: core logic (insertion, dedupe, truncation) is framework agnostic.
 - Performance safety: O(1) updates; fixed maximum length (default 5).

The actual highlight visualization (e.g., fading outline) can be implemented later.
This milestone delivers the data & event emission so downstream effects can hook in.
"""

from __future__ import annotations
from dataclasses import dataclass
from typing import Deque, List, Optional, Any
from collections import deque
from time import perf_counter

try:  # Optional Qt import; logic does not require it for tests
    from PyQt6.QtCore import QObject
except Exception:  # pragma: no cover
    QObject = object  # type: ignore

from .service_locator import services
from .event_bus import EventBus

__all__ = ["FocusTrailService", "get_focus_trail_service"]


@dataclass
class FocusEntry:
    object_id: int
    timestamp: float


class FocusTrailService:
    """Stores recent focus path for keyboard-based navigation.

    A very small fixed-size deque is used. Adding an object moves it to the
    front (most recent). Duplicate suppression ensures uniqueness in the path.
    """

    def __init__(self, capacity: int = 5) -> None:
        if capacity < 1:
            raise ValueError("capacity must be >= 1")
        self._capacity = capacity
        self._trail: Deque[FocusEntry] = deque(maxlen=capacity)

    # Pure logic -------------------------------------------------------
    def add_focus_object(self, obj: Any) -> None:
        oid = id(obj)
        # Remove any prior entry with same id
        self._trail = deque([e for e in self._trail if e.object_id != oid], maxlen=self._capacity)
        self._trail.appendleft(FocusEntry(object_id=oid, timestamp=perf_counter()))
        # Publish event (best effort)
        try:  # pragma: no cover - event bus integration
            bus = services.get_typed("event_bus", EventBus)
            bus.publish(
                "focus_trail_updated",
                {"trail": [e.object_id for e in self._trail]},
            )
        except Exception:
            pass

    def trail_ids(self) -> List[int]:
        return [e.object_id for e in self._trail]

    def clear(self) -> None:
        self._trail.clear()

    def capacity(self) -> int:
        return self._capacity


def get_focus_trail_service() -> FocusTrailService:
    svc = services.try_get("focus_trail_service")
    if svc is None:
        svc = FocusTrailService()
        services.register("focus_trail_service", svc)
    return svc
