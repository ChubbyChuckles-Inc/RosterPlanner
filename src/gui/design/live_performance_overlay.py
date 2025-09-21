"""Live performance overlay metrics (Milestone 0.46).

Developer-only instrumentation module to aggregate lightweight paint / layout
timings that can be surfaced in a future on-screen overlay widget. The GUI
widget itself will be implemented later; this module focuses on data capture
and summarization with zero dependency on PyQt so it is unit-testable.

Features
--------
 - Enable/disable global capture (fast early exit when disabled)
 - Record paint cycles (timestamp, duration_ms, layout_passes, widgets_painted)
 - Maintain ring buffer (capacity configurable; default 600 ~ 10 minutes @ 1Hz)
 - Compute rolling stats: count, avg, min, max, p50, p95, p99
 - Derived metrics: paints per second (approx), layout intensity (avg layout passes per paint)
 - Clear/reset API
 - Simple textual summary builder (for logging or future overlay rendering)

Design Decisions
----------------
 - Use time.perf_counter for high resolution timing (caller supplies duration to avoid double measurement).
 - Percentiles computed via copy + nth selection (data size small enough; optimization later if needed).
 - Keep data immutable after capture (dataclass frozen) to simplify reasoning.
 - Avoid external libs (numpy, statistics) to minimize dependencies.
 - Guard against negative or NaN durations with validation (ignored with flag).

Future Extensions (Out of Scope Now)
------------------------------------
 - GC pause tracking
 - Main thread blockage detection (long gaps between paints)
 - Integration with interaction latency recorder
 - GPU vs CPU time split (if Qt exposes)
 - Adaptive warning thresholds (color highlighting for overlay)
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import List, Optional, Dict, Any, Sequence
import math
import time

__all__ = [
    "PaintSample",
    "enable_capture",
    "disable_capture",
    "is_enabled",
    "record_paint_cycle",
    "get_paint_samples",
    "clear_paint_samples",
    "compute_stats",
    "build_summary",
]


@dataclass(frozen=True)
class PaintSample:
    timestamp: float  # epoch seconds
    duration_ms: float
    layout_passes: int
    widgets_painted: int


_ENABLED: bool = True
_CAPACITY: int = 600
_SAMPLES: List[PaintSample] = []
_IGNORED_INVALID: int = 0


def enable_capture() -> None:
    """Enable performance capture globally."""
    global _ENABLED
    _ENABLED = True


def disable_capture() -> None:
    """Disable performance capture (fast path stops recording)."""
    global _ENABLED
    _ENABLED = False


def is_enabled() -> bool:
    return _ENABLED


def record_paint_cycle(
    duration_ms: float,
    layout_passes: int = 0,
    widgets_painted: int = 0,
    *,
    timestamp: Optional[float] = None,
) -> Optional[PaintSample]:
    """Record a paint/layout cycle.

    Caller is expected to measure duration externally (e.g., around the Qt
    event loop paint or a render function) and feed it here.

    Returns the created sample or None if capture disabled or invalid.
    """
    global _IGNORED_INVALID
    if not _ENABLED:
        return None
    if not math.isfinite(duration_ms) or duration_ms < 0:
        _IGNORED_INVALID += 1
        return None
    ts = timestamp if timestamp is not None else time.time()
    sample = PaintSample(ts, float(duration_ms), int(layout_passes), int(widgets_painted))
    if len(_SAMPLES) >= _CAPACITY:
        _SAMPLES.pop(0)
    _SAMPLES.append(sample)
    return sample


def get_paint_samples() -> List[PaintSample]:
    return list(_SAMPLES)


def clear_paint_samples() -> None:
    _SAMPLES.clear()
    global _IGNORED_INVALID
    _IGNORED_INVALID = 0


def _percentile(sorted_values: Sequence[float], p: float) -> float:
    if not sorted_values:
        return 0.0
    if p <= 0:
        return sorted_values[0]
    if p >= 100:
        return sorted_values[-1]
    k = (len(sorted_values) - 1) * (p / 100.0)
    f = math.floor(k)
    c = math.ceil(k)
    if f == c:
        return sorted_values[int(k)]
    d0 = sorted_values[f] * (c - k)
    d1 = sorted_values[c] * (k - f)
    return d0 + d1


def compute_stats() -> Dict[str, Any]:
    """Compute rolling statistics for current samples.

    Returns keys: count, avg_ms, min_ms, max_ms, p50_ms, p95_ms, p99_ms,
    paints_per_sec_est, layout_intensity, widgets_avg, ignored_invalid.
    """
    samples = list(_SAMPLES)
    count = len(samples)
    if count == 0:
        return {
            "count": 0,
            "avg_ms": 0.0,
            "min_ms": 0.0,
            "max_ms": 0.0,
            "p50_ms": 0.0,
            "p95_ms": 0.0,
            "p99_ms": 0.0,
            "paints_per_sec_est": 0.0,
            "layout_intensity": 0.0,
            "widgets_avg": 0.0,
            "ignored_invalid": _IGNORED_INVALID,
        }
    durations = [s.duration_ms for s in samples]
    durations_sorted = sorted(durations)
    layout_total = sum(s.layout_passes for s in samples)
    widgets_total = sum(s.widgets_painted for s in samples)
    span_sec = max(samples[-1].timestamp - samples[0].timestamp, 0.0001)
    paints_per_sec = count / span_sec
    stats = {
        "count": count,
        "avg_ms": sum(durations) / count,
        "min_ms": durations_sorted[0],
        "max_ms": durations_sorted[-1],
        "p50_ms": _percentile(durations_sorted, 50),
        "p95_ms": _percentile(durations_sorted, 95),
        "p99_ms": _percentile(durations_sorted, 99),
        "paints_per_sec_est": paints_per_sec,
        "layout_intensity": layout_total / count,
        "widgets_avg": widgets_total / count,
        "ignored_invalid": _IGNORED_INVALID,
    }
    return stats


def build_summary() -> str:
    st = compute_stats()
    if st["count"] == 0:
        return "No paint samples recorded."
    return (
        "PaintSamples count={count} avg={avg_ms:.1f}ms p95={p95_ms:.1f}ms "
        "max={max_ms:.1f}ms Hz={paints_per_sec_est:.2f} layout_avg={layout_intensity:.2f} "
        "widgets_avg={widgets_avg:.1f} ignored={ignored_invalid}".format(**st)
    )
