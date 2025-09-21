import time

from gui.design.live_performance_overlay import (
    enable_capture,
    disable_capture,
    is_enabled,
    record_paint_cycle,
    get_paint_samples,
    clear_paint_samples,
    compute_stats,
    build_summary,
)


def test_enable_disable_and_record():
    clear_paint_samples()
    disable_capture()
    assert is_enabled() is False
    assert record_paint_cycle(5.0) is None  # ignored while disabled
    enable_capture()
    assert is_enabled() is True
    s = record_paint_cycle(5.0, layout_passes=2, widgets_painted=10, timestamp=1000.0)
    assert s is not None
    samples = get_paint_samples()
    assert len(samples) == 1
    assert samples[0].duration_ms == 5.0
    assert samples[0].layout_passes == 2
    assert samples[0].widgets_painted == 10


def test_invalid_negative_duration_ignored():
    clear_paint_samples()
    enable_capture()
    record_paint_cycle(-1.0)
    assert len(get_paint_samples()) == 0


def test_stats_calculation_and_percentiles():
    clear_paint_samples()
    enable_capture()
    # deterministic timestamps increasing 1 sec
    base = 1000.0
    durations = [10, 20, 30, 40, 50]
    for i, d in enumerate(durations):
        record_paint_cycle(d, layout_passes=i, widgets_painted=i * 2, timestamp=base + i)
    stats = compute_stats()
    assert stats["count"] == 5
    assert stats["min_ms"] == 10
    assert stats["max_ms"] == 50
    assert round(stats["avg_ms"], 2) == 30.0
    # p50 ~ median (30)
    assert stats["p50_ms"] == 30
    assert stats["p95_ms"] >= 40  # interpolation may give >40, <=50
    assert stats["layout_intensity"] == sum(range(5)) / 5
    assert stats["widgets_avg"] == sum(i * 2 for i in range(5)) / 5
    assert stats["paints_per_sec_est"] > 0  # span is 4s, count 5 => ~1.25 Hz


def test_summary_empty_and_nonempty():
    clear_paint_samples()
    disable_capture()
    # empty summary
    assert build_summary().startswith("No paint samples")
    enable_capture()
    record_paint_cycle(12.34, layout_passes=1, widgets_painted=3, timestamp=2000.0)
    out = build_summary()
    assert "count=1" in out
    assert "avg=12.3" in out or "avg=12.34" in out


def test_capacity_ring_buffer():
    clear_paint_samples()
    enable_capture()
    # push more than capacity small for test (override internal purposely)
    # We cannot change capacity directly (internal), so rely on default 600; push 610 and ensure length <= 600.
    for i in range(610):
        record_paint_cycle(1.0, timestamp=3000.0 + i)
    samples = get_paint_samples()
    assert len(samples) <= 600
    # ensure samples are the most recent (timestamp monotonic check)
    ts_list = [s.timestamp for s in samples]
    assert ts_list == sorted(ts_list)
