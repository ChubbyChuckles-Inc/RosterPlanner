"""Health metrics service (Milestone 1.10).

Collects lightweight runtime health indicators for optional overlay:
 - FPS (frame ticks per second) based on calls to frame_tick()
 - Memory usage (tracemalloc snapshot)
 - DB query/sec (pluggable provider function returning cumulative count)

Design Goals:
 - Headless-test friendly (time & memory capture abstractions injectable)
 - No hard dependency on PyQt; frame_tick called by GUI render loop instrumentation later
 - Constant time operations; uses fixed-size deques for frame times & samples
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Callable, Deque, List, Optional
from collections import deque
import time
import tracemalloc

__all__ = ["HealthSample", "HealthMetricsService"]


@dataclass(frozen=True)
class HealthSample:
    timestamp: float
    fps: float
    mem_current_kb: int
    mem_peak_kb: int
    db_qps: float


class HealthMetricsService:
    def __init__(
        self,
        *,
        frame_window_seconds: float = 5.0,
        sample_capacity: int = 120,
        time_func: Callable[[], float] | None = None,
    ) -> None:
        self._time = time_func or time.perf_counter
        self._frame_window = frame_window_seconds
        self._frame_times: Deque[float] = deque()
        self._samples: Deque[HealthSample] = deque(maxlen=sample_capacity)
        self._db_counter_provider: Callable[[], int] | None = None
        self._last_db_count: int = 0
        self._last_db_time: float = self._time()
        # Ensure tracemalloc started (idempotent)
        if not tracemalloc.is_tracing():  # pragma: no cover - trivial guard
            tracemalloc.start()

    # ------------------------------------------------------------------
    # External hooks
    # ------------------------------------------------------------------
    def register_db_counter(self, provider: Callable[[], int]) -> None:
        self._db_counter_provider = provider
        self._last_db_count = provider()
        self._last_db_time = self._time()

    def frame_tick(self) -> None:
        now = self._time()
        self._frame_times.append(now)
        # Discard frames outside window
        cutoff = now - self._frame_window
        while self._frame_times and self._frame_times[0] < cutoff:
            self._frame_times.popleft()

    # ------------------------------------------------------------------
    # Sampling
    # ------------------------------------------------------------------
    def sample(self) -> HealthSample:
        now = self._time()
        # FPS computation
        frame_count = len(self._frame_times)
        if frame_count >= 2:
            span = self._frame_times[-1] - self._frame_times[0]
            fps = frame_count / span if span > 0 else 0.0
        else:
            fps = 0.0
        current, peak = tracemalloc.get_traced_memory()
        mem_current_kb = int(current / 1024)
        mem_peak_kb = int(peak / 1024)
        # DB queries per second (since last sample)
        db_qps = 0.0
        if self._db_counter_provider is not None:
            total = self._db_counter_provider()
            dt = now - self._last_db_time
            delta = total - self._last_db_count
            if dt > 0 and delta >= 0:
                db_qps = delta / dt
            self._last_db_count = total
            self._last_db_time = now
        sample = HealthSample(
            timestamp=now,
            fps=round(fps, 2),
            mem_current_kb=mem_current_kb,
            mem_peak_kb=mem_peak_kb,
            db_qps=round(db_qps, 2),
        )
        self._samples.append(sample)
        return sample

    # ------------------------------------------------------------------
    # Introspection
    # ------------------------------------------------------------------
    def recent_samples(self) -> List[HealthSample]:
        return list(self._samples)

    def clear(self) -> None:
        self._samples.clear()
        self._frame_times.clear()
