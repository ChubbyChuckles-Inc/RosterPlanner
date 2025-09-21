import time
import pytest

from gui.services.event_bus import EventBus, GUIEvent
from gui.services.service_locator import services
from gui.services import event_tracing


@pytest.fixture()
def bus():
    bus = EventBus()
    # Use override_context if available for isolation; fallback to allow_override
    try:
        override_ctx = services.override_context(event_bus=bus)  # type: ignore[attr-defined]
    except AttributeError:
        override_ctx = None
        services.register("event_bus", bus, allow_override=True)
    if override_ctx:
        with override_ctx:
            yield bus
    else:
        try:
            yield bus
        finally:
            services._services.pop("event_bus", None)  # type: ignore[attr-defined]


def test_tracing_capture_basic(bus: EventBus):
    event_tracing.enable_event_tracing(capacity=5)

    for i in range(3):
        bus.publish(GUIEvent.DATA_REFRESHED, i)

    traces = event_tracing.get_recent_event_traces()
    assert len(traces) == 3
    assert all(t.name == GUIEvent.DATA_REFRESHED.value for t in traces)
    # summaries correspond to int payloads converted to string
    assert [t.summary for t in traces] == ["0", "1", "2"]
    ts = [t.timestamp for t in traces]
    assert ts == sorted(ts)  # monotonic


def test_tracing_capacity_ring_buffer(bus: EventBus):
    event_tracing.enable_event_tracing(capacity=3)
    for i in range(6):
        bus.publish(GUIEvent.SELECTION_CHANGED, i)
    traces = event_tracing.get_recent_event_traces()
    assert len(traces) == 3
    # only last three kept
    assert [t.summary for t in traces] == ["3", "4", "5"]


def test_disable_tracing_stops_capture(bus: EventBus):
    event_tracing.enable_event_tracing(capacity=10)
    bus.publish(GUIEvent.STATS_UPDATED, 1)
    assert len(event_tracing.get_recent_event_traces()) == 1
    event_tracing.disable_event_tracing()
    bus.publish(GUIEvent.STATS_UPDATED, 2)
    # still returns previous entries but no new ones appended
    traces = event_tracing.get_recent_event_traces()
    assert len(traces) == 1
    assert traces[0].summary == "1"


def test_tracing_noop_when_disabled(bus: EventBus):
    # ensure calling disable first is harmless
    event_tracing.disable_event_tracing()
    bus.publish(GUIEvent.DATA_REFRESHED)
    assert event_tracing.get_recent_event_traces() == []
