import pytest

from gui.services.theme_service import ThemeService
from gui.services.event_bus import EventBus, GUIEvent
from gui.services.service_locator import services


@pytest.fixture()
def setup_services():
    # Ensure clean locator state for event_bus and theme_service
    bus = EventBus()
    services.register("event_bus", bus, allow_override=True)
    theme = ThemeService.create_default()
    services.register("theme_service", theme, allow_override=True)
    yield bus, theme
    # Cleanup
    services._services.pop("event_bus", None)  # type: ignore[attr-defined]
    services._services.pop("theme_service", None)  # type: ignore[attr-defined]


def test_theme_variant_switch_emits_event(setup_services):
    bus, theme = setup_services
    received = []

    def handler(evt):
        received.append(evt.payload)

    bus.subscribe(GUIEvent.THEME_CHANGED, handler)
    diff = theme.set_variant("high-contrast")
    assert not diff.no_changes
    assert received, "Expected theme changed event"
    payload = received[-1]
    assert "changed" in payload and "count" in payload
    assert payload["count"] >= 1


def test_theme_accent_change_emits_event(setup_services):
    bus, theme = setup_services
    received = []

    def handler(evt):
        received.append(evt.payload)

    bus.subscribe(GUIEvent.THEME_CHANGED, handler)
    diff = theme.set_accent("#FF5722")
    assert not diff.no_changes
    assert received
    assert received[-1]["count"] >= 1
