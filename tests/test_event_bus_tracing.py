from gui.app.bootstrap import create_app


def test_tracing_disabled_by_default():
    ctx = create_app(headless=True)
    bus = ctx.services.get("event_bus")
    bus.publish("a")
    assert bus.recent_traces() == []


def test_enable_tracing_and_capture():
    ctx = create_app(headless=True)
    bus = ctx.services.get("event_bus")
    bus.enable_tracing(True)
    for i in range(3):
        bus.publish("evt", {"i": i})
    traces = bus.recent_traces()
    assert len(traces) == 3
    names = [t[0] for t in traces]
    assert names == ["evt", "evt", "evt"]


def test_tracing_capacity_ring_buffer():
    ctx = create_app(headless=True)
    bus = ctx.services.get("event_bus")
    bus.enable_tracing(True, capacity=5)
    for i in range(12):
        bus.publish(f"evt{i}")
    traces = bus.recent_traces()
    assert len(traces) == 5
    # Should retain only last 5 events
    last_names = [t[0] for t in traces]
    assert last_names == [f"evt{i}" for i in range(7, 12)]


def test_disable_tracing_stops_new_entries():
    ctx = create_app(headless=True)
    bus = ctx.services.get("event_bus")
    bus.enable_tracing(True)
    bus.publish("one")
    bus.enable_tracing(False)
    bus.publish("two")
    names = [t[0] for t in bus.recent_traces()]
    assert names == ["one"]