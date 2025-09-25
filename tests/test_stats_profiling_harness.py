"""Performance baseline test for analytics stack (Milestone 6.9).

Generates a synthetic dataset and measures timing + memory for:
 - Batch KPI computations
 - Division strength index + history
 - Rolling form calculations
 - Match outcome predictor passes
 - Cache effectiveness (first vs second lookup)

Thresholds are intentionally generous on initial introduction; they can be
tightened once stability and headroom are confirmed. An environment variable
`STATS_PROF_RELAX=1` may be used to relax failures into xfail on slow CI.
"""

from __future__ import annotations

import os
import sqlite3
import time
import pytest

from gui.services.stats_profiling_harness import run_stats_profiling

# ------------- Threshold Configuration ---------------------------------
THRESHOLDS = {
    "kpis": 1.2,  # seconds
    "division_strength": 0.8,
    "division_strength_history": 1.0,
    "rolling_form": 1.2,
    "predictor": 1.0,
    "cache_first": 0.5,
    "cache_second": 0.05,  # should be very fast on hit
}

PEAK_MEMORY_BYTES = 50 * 1024 * 1024  # 50 MB generous initial cap
RELAX_ENV = "STATS_PROF_RELAX"


@pytest.mark.performance
def test_stats_profiling_baseline():
    conn = sqlite3.connect(":memory:")
    start_total = time.perf_counter()
    result = run_stats_profiling(conn)
    total_duration = time.perf_counter() - start_total

    # Sanity: dataset sizes within expected ranges
    assert result.dataset["teams_per_division"] >= 8
    assert result.dataset["players_per_team"] >= 4
    assert result.dataset["matches"] > 20

    relax = os.environ.get(RELAX_ENV) == "1"
    failures = []
    for phase, limit in THRESHOLDS.items():
        dur = result.durations.get(phase)
        assert dur is not None, f"Missing duration for {phase}"  # structural
        if dur > limit:
            failures.append(f"{phase}: {dur:.3f}s > {limit:.2f}s")

    if result.peak_memory_bytes > PEAK_MEMORY_BYTES:
        failures.append(
            f"peak_memory: {result.peak_memory_bytes/1024/1024:.2f}MB > {PEAK_MEMORY_BYTES/1024/1024:.1f}MB"
        )

    # Optional informational assertion: cache speedup should be meaningful
    speedup = result.cache_speedup_ratio
    if speedup is not None and speedup < 1.2:  # <20% speedup indicates potential regression
        failures.append(f"cache speedup low: {speedup:.2f}x (<1.2x)")

    if failures:
        msg = "; ".join(failures)
        if relax:
            pytest.xfail(f"Profiling thresholds exceeded (relaxed): {msg}")
        else:
            pytest.fail(f"Profiling thresholds exceeded: {msg}")

    # Emit summary for CI logs
    print("[PERF][STATS] durations:")
    for k, v in sorted(result.durations.items()):
        print(f"  {k:<28} {v:.4f}s (limit {THRESHOLDS.get(k,'-')})")
    print(
        f"[PERF][STATS] peak memory: {result.peak_memory_bytes/1024/1024:.2f}MB (limit {PEAK_MEMORY_BYTES/1024/1024:.1f}MB)"
    )
    if speedup is not None:
        print(f"[PERF][STATS] cache speedup: {speedup:.2f}x")
