"""Startup timing instrumentation utilities (Milestone 1.2.2).

The timing logger is intentionally lightweight and allocation-conscious.
It collects named phase durations during application bootstrap so we can:
 - Identify slow phases early (I/O, heavy imports, future DB migrations, etc.)
 - Establish a baseline for performance regression tracking
 - Feed future diagnostics panels / developer console

Design goals:
 - Zero external dependencies
 - Context manager based API for ergonomic phase measurement
 - Safe re-entrancy prevention (cannot begin a new phase before ending the last)
 - Immutable event records (dataclass with computed duration property)
 - Serialization helper for logging / telemetry (as_dict)
"""

from __future__ import annotations

from dataclasses import dataclass
from time import perf_counter
from typing import Iterator, List

__all__ = [
    "TimingEvent",
    "TimingLogger",
]


@dataclass
class TimingEvent:
    name: str
    start: float
    end: float

    @property
    def duration(self) -> float:  # seconds
        return self.end - self.start


class TimingLogger:
    """Collects timing events for labelled phases.

    Usage:
        t = TimingLogger()
        with t.measure("load_tokens"):
            load_tokens()
        t.stop()

    After stop(), no further events may be added.
    """

    def __init__(self) -> None:
        self._started_at = perf_counter()
        self._events: List[TimingEvent] = []
        self._current_name: str | None = None
        self._current_start: float | None = None
        self._stopped: bool = False
        self._stopped_at: float | None = None

    # ------------------------------------------------------------------
    # Core control
    # ------------------------------------------------------------------
    @property
    def started_at(self) -> float:
        return self._started_at

    @property
    def stopped_at(self) -> float | None:
        return self._stopped_at

    def stop(self) -> None:
        if not self._stopped:
            if self._current_name is not None:
                # Auto-close dangling phase to avoid corrupt data.
                self.end()
            self._stopped_at = perf_counter()
            self._stopped = True

    # ------------------------------------------------------------------
    # Phase measurement API
    # ------------------------------------------------------------------
    def begin(self, name: str) -> None:
        if self._stopped:
            raise RuntimeError("TimingLogger already stopped")
        if self._current_name is not None:
            raise RuntimeError(
                f"Attempted to begin phase '{name}' while phase "
                f"'{self._current_name}' still active"
            )
        self._current_name = name
        self._current_start = perf_counter()

    def end(self) -> None:
        if self._current_name is None or self._current_start is None:
            raise RuntimeError("No active timing phase to end")
        end_time = perf_counter()
        self._events.append(
            TimingEvent(name=self._current_name, start=self._current_start, end=end_time)
        )
        self._current_name = None
        self._current_start = None

    # Convenience context manager
    class _PhaseCtx:
        def __init__(self, logger: "TimingLogger", name: str) -> None:
            self._logger = logger
            self._name = name

        def __enter__(self) -> "TimingLogger._PhaseCtx":  # noqa: D401 (simple)
            self._logger.begin(self._name)
            return self

        def __exit__(self, exc_type, exc, tb) -> None:  # noqa: D401
            # Even if an exception occurs we still record the elapsed time.
            self._logger.end()

    def measure(self, name: str) -> "TimingLogger._PhaseCtx":
        return TimingLogger._PhaseCtx(self, name)

    # ------------------------------------------------------------------
    # Data access
    # ------------------------------------------------------------------
    @property
    def events(self) -> List[TimingEvent]:
        return list(self._events)  # defensive copy

    @property
    def total_duration(self) -> float:
        if self._stopped and self._stopped_at is not None:
            return self._stopped_at - self._started_at
        # If not stopped, approximate with now.
        return perf_counter() - self._started_at

    def as_dict(self) -> dict:
        return {
            "started_at": self._started_at,
            "stopped_at": self._stopped_at,
            "total_duration": self.total_duration,
            "events": [
                {
                    "name": e.name,
                    "start": e.start,
                    "end": e.end,
                    "duration": e.duration,
                }
                for e in self._events
            ],
        }

    # Iterable support (iterate over events)
    def __iter__(self) -> Iterator[TimingEvent]:
        return iter(self._events)

    # String repr: concise summary
    def __repr__(self) -> str:  # pragma: no cover - trivial
        return (
            f"TimingLogger(events={len(self._events)}, "
            f"total={self.total_duration:.4f}s, stopped={self._stopped})"
        )
