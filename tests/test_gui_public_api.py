def test_gui_public_api_symbols():
    import gui

    # Core symbols should exist
    assert hasattr(gui, "services")
    assert hasattr(gui, "ServiceLocator")
    assert hasattr(gui, "ServiceAlreadyRegisteredError")
    assert hasattr(gui, "ServiceNotFoundError")
    assert hasattr(gui, "EventBus")
    assert hasattr(gui, "GUIEvent")
    assert hasattr(gui, "Event")
    # create_application is optional; should exist (may be None if bootstrap not present)
    assert hasattr(gui, "create_application")
    # design namespace available
    assert hasattr(gui, "design")


def test_event_bus_basic_publish_subscribe():
    import gui

    bus = gui.EventBus()
    received = []

    def handler(evt):  # noqa: D401 - simple local handler
        received.append(evt.name)

    bus.subscribe(gui.GUIEvent.STARTUP_COMPLETE, handler)
    bus.publish(gui.GUIEvent.STARTUP_COMPLETE)
    assert received == [gui.GUIEvent.STARTUP_COMPLETE.value]


def test_service_locator_register_and_get():
    import gui

    gui.services.register("foo", 123)
    assert gui.services.get("foo") == 123


def test_design_namespace_access():
    import gui

    # Spot-check a couple of design exports reachable via namespaced import
    assert hasattr(gui.design, "build_chart_palette")
    assert hasattr(gui.design, "ComponentMaturity")
