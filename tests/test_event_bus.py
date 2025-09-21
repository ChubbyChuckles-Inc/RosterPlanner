from gui.app.bootstrap import create_app
from gui.services.event_bus import GUIEvent, EventBus


def test_event_bus_service_registration():
    ctx = create_app(headless=True)
    bus = ctx.services.get("event_bus")
    assert isinstance(bus, EventBus)


def test_subscribe_publish_basic():
    ctx = create_app(headless=True)
    bus: EventBus = ctx.services.get("event_bus")
    received = []

    def handler(evt):
        received.append((evt.name, evt.payload))

    bus.subscribe(GUIEvent.THEME_CHANGED, handler)
    bus.publish(GUIEvent.THEME_CHANGED, {"dark": True})
    assert received == [(GUIEvent.THEME_CHANGED.value, {"dark": True})]


def test_once_subscription():
    ctx = create_app(headless=True)
    bus: EventBus = ctx.services.get("event_bus")
    count = 0

    def incr(_):
        nonlocal count
        count += 1

    bus.subscribe(GUIEvent.STARTUP_COMPLETE, incr, once=True)
    bus.publish(GUIEvent.STARTUP_COMPLETE)
    bus.publish(GUIEvent.STARTUP_COMPLETE)
    assert count == 1  # second publish ignored


def test_error_isolation():
    ctx = create_app(headless=True)
    bus: EventBus = ctx.services.get("event_bus")
    order = []

    def bad(_):
        order.append("bad")
        raise RuntimeError("boom")

    def good(_):
        order.append("good")

    bus.subscribe("custom", bad)
    bus.subscribe("custom", good)
    bus.publish("custom", 123)
    # Both handlers executed despite error
    assert order == ["bad", "good"]
    assert len(bus.errors) == 1
