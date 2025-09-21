"""Tests for interaction latency instrumentation (Milestone 0.22)."""

import time
from gui.design.interaction_latency import (
    instrument_latency,
    latency_block,
    get_latency_records,
    clear_latency_records,
    list_thresholds,
    LatencyThreshold,
    register_threshold,
)


def _sleep_ms(ms: float):
    time.sleep(ms / 1000.0)


def setup_function(_):  # noqa: D401
    clear_latency_records()


def test_decorator_records_latency():
    @instrument_latency("decorated-op")
    def op():
        _sleep_ms(5)

    op()
    recs = get_latency_records()
    assert len(recs) == 1
    assert recs[0].event_label == "decorated-op"
    assert recs[0].duration_ms >= 5


def test_context_manager_records_latency():
    with latency_block("ctx-op"):
        _sleep_ms(12)
    recs = get_latency_records()
    assert recs[-1].event_label == "ctx-op"
    assert recs[-1].duration_ms >= 12


def test_threshold_exceeded_flag():
    # Ensure a very small custom threshold triggers exceed logic easily
    register_threshold(
        LatencyThreshold(id="tiny", max_ms=1.0, severity="warning", description="tiny")
    )
    clear_latency_records()

    @instrument_latency("slow-op")
    def slow():
        _sleep_ms(10)

    slow()
    rec = get_latency_records()[-1]
    assert rec.threshold_exceeded is not None


def test_multiple_calls_ring_buffer_order():
    for i in range(3):
        with latency_block(f"iter-{i}"):
            _sleep_ms(2)
    recs = get_latency_records()
    labels = [r.event_label for r in recs[-3:]]
    assert labels == ["iter-0", "iter-1", "iter-2"]


def test_clear_records():
    with latency_block("to-clear"):
        _sleep_ms(1)
    assert get_latency_records()
    clear_latency_records()
    assert get_latency_records() == []
