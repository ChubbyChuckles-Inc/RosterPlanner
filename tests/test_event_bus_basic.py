from gui.services.event_bus import EventBus, GUIEvent


def test_subscribe_and_publish_order():
    bus = EventBus()
    order = []

    def h1(e):
        order.append(("h1", e.name))

    def h2(e):
        order.append(("h2", e.name))

    bus.subscribe(GUIEvent.SELECTION_CHANGED, h1)
    bus.subscribe(GUIEvent.SELECTION_CHANGED, h2)
    bus.publish(GUIEvent.SELECTION_CHANGED, {"id": 1})
    assert order == [
        ("h1", GUIEvent.SELECTION_CHANGED.value),
        ("h2", GUIEvent.SELECTION_CHANGED.value),
    ]


def test_once_subscription():
    bus = EventBus()
    calls = []
    bus.subscribe(GUIEvent.DATA_REFRESHED, lambda e: calls.append(e.name), once=True)
    bus.publish(GUIEvent.DATA_REFRESHED)
    bus.publish(GUIEvent.DATA_REFRESHED)
    assert calls == [GUIEvent.DATA_REFRESHED.value]


def test_unsubscribe():
    bus = EventBus()
    calls = []
    sub = bus.subscribe(GUIEvent.STATS_UPDATED, lambda e: calls.append(1))
    bus.publish(GUIEvent.STATS_UPDATED)
    sub.cancel()
    bus.unsubscribe(sub)
    bus.publish(GUIEvent.STATS_UPDATED)
    assert calls == [1]


def test_error_isolation():
    bus = EventBus()
    calls = []

    def bad(e):
        raise RuntimeError("boom")

    def good(e):
        calls.append("ok")

    bus.subscribe(GUIEvent.DATA_REFRESHED, bad)
    bus.subscribe(GUIEvent.DATA_REFRESHED, good)
    bus.publish(GUIEvent.DATA_REFRESHED)
    assert calls == ["ok"]
    assert len(bus.errors) == 1
