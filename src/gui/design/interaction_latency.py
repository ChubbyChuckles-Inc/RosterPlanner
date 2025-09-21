"""Interaction latency instrumentation (Milestone 0.22).

Provides lightweight tooling to record and inspect event→handler→completion
latencies to surface outliers (>100ms default) threatening perceived UI
responsiveness. Pure-Python & framework-agnostic for unit testability.

Concepts
--------
LatencyRecord: Immutable data describing one measured span.
LatencyThreshold: Configurable threshold categories (e.g., warning, critical).
Registry: In-memory ring buffer of recent latency records.
Decorator / Context Manager: Easy instrumentation of functions and scoped blocks.

Design Decisions
----------------
 - Avoid wall-clock monotonic drift issues by using time.perf_counter.
 - Minimal overhead: single perf_counter pair + conditional store.
 - O(1) append ring buffer; caller can snapshot for aggregation.
 - Threshold evaluation at record time for simpler filtering.
 - Pure data objects; integration with logging/GUI overlay deferred.

Future Extensions
-----------------
 - Add percentile summary helper.
 - Expose async instrumentation variant.
 - Integrate with planned performance overlay (Milestone 1.x / P?).
"""

from __future__ import annotations

import time
from dataclasses import dataclass
from typing import Callable, List, Optional, Sequence, Any, Dict

__all__ = [
    "LatencyRecord",
    "LatencyThreshold",
    "LatencyRecorder",
    "instrument_latency",
    "latency_block",
    "get_latency_records",
    "clear_latency_records",
    "register_threshold",
    "list_thresholds",
]


@dataclass(frozen=True)
class LatencyRecord:
    event_label: str
    duration_ms: float
    timestamp: float
    threshold_exceeded: Optional[str]  # id of threshold exceeded if any


@dataclass(frozen=True)
class LatencyThreshold:
    id: str
    max_ms: float
    severity: str  # e.g., 'warning', 'critical'
    description: str

    def test(self, duration_ms: float) -> bool:
        return duration_ms > self.max_ms


class LatencyRecorder:
    """Ring buffer of recent latency records with threshold evaluation."""

    def __init__(self, capacity: int = 500):
        self._capacity = capacity
        self._records: List[LatencyRecord] = []

    def add(
        self, label: str, duration_ms: float, thresholds: Sequence[LatencyThreshold]
    ) -> LatencyRecord:
        threshold_id = None
        # Evaluate highest severity first (assumes thresholds sorted by max_ms ascending so highest severity implies larger max? we'll explicit sort by max_ms asc)
        exceeded: List[str] = [t.id for t in thresholds if t.test(duration_ms)]
        if exceeded:
            # choose threshold with smallest max_ms exceeded first for granularity
            # constructing lookup:
            by_id: Dict[str, float] = {t.id: t.max_ms for t in thresholds}
            exceeded.sort(key=lambda tid: by_id[tid])
            threshold_id = exceeded[0]
        rec = LatencyRecord(label, duration_ms, time.time(), threshold_id)
        if len(self._records) >= self._capacity:
            # drop oldest
            self._records.pop(0)
        self._records.append(rec)
        return rec

    def list(self) -> List[LatencyRecord]:
        return list(self._records)

    def clear(self) -> None:
        self._records.clear()


_RECORDER = LatencyRecorder()
_THRESHOLDS: List[LatencyThreshold] = []


def register_threshold(threshold: LatencyThreshold) -> None:
    if any(t.id == threshold.id for t in _THRESHOLDS):
        raise ValueError("Duplicate threshold id: %s" % threshold.id)
    _THRESHOLDS.append(threshold)
    # Keep thresholds sorted ascending by max_ms for evaluation ordering
    _THRESHOLDS.sort(key=lambda t: t.max_ms)


def list_thresholds() -> List[LatencyThreshold]:
    return list(_THRESHOLDS)


# Default thresholds
register_threshold(
    LatencyThreshold(
        id="slow",
        max_ms=100.0,
        severity="warning",
        description="Exceeds 100ms responsiveness guideline",
    )
)
register_threshold(
    LatencyThreshold(
        id="very-slow",
        max_ms=250.0,
        severity="critical",
        description="Exceeds 250ms noticeable lag",
    )
)


def instrument_latency(label: str) -> Callable[[Callable[..., Any]], Callable[..., Any]]:
    """Decorator to measure synchronous function latency in ms.

    Examples
    --------
    @instrument_latency("load-team-data")
    def load_team(...):
        ...
    """

    def decorator(func: Callable[..., Any]) -> Callable[..., Any]:
        def wrapper(*args: Any, **kwargs: Any) -> Any:
            start = time.perf_counter()
            try:
                return func(*args, **kwargs)
            finally:
                duration = (time.perf_counter() - start) * 1000.0
                _RECORDER.add(label, duration, _THRESHOLDS)

        return wrapper

    return decorator


class latency_block:
    """Context manager to instrument arbitrary code blocks.

    Usage
    -----
    with latency_block("parse-division"):
        parse_division_html(...)
    """

    def __init__(self, label: str):
        self._label = label
        self._start: Optional[float] = None

    def __enter__(self) -> "latency_block":  # noqa: D401
        self._start = time.perf_counter()
        return self

    def __exit__(self, exc_type, exc, tb) -> None:  # noqa: D401
        if self._start is None:
            return
        duration = (time.perf_counter() - self._start) * 1000.0
        _RECORDER.add(self._label, duration, _THRESHOLDS)


def get_latency_records() -> List[LatencyRecord]:
    return _RECORDER.list()


def clear_latency_records() -> None:
    _RECORDER.clear()
