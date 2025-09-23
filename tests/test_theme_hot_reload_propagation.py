import os
import pytest
from PyQt6.QtWidgets import QApplication, QLabel

from gui.components.theme_aware import ThemeAwareMixin
from gui.services.service_locator import services
from gui.services.theme_service import ThemeService
from gui.services.event_bus import EventBus, GUIEvent

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

class DemoLabel(QLabel, ThemeAwareMixin):
    def __init__(self):
        super().__init__("demo")
        self.called = 0
        self.last_changed = None
    def on_theme_changed(self, theme, changed_keys):  # type: ignore[override]
        self.called += 1
        self.last_changed = tuple(changed_keys)
        # Simple visual mutation: update object name for test (not user visible)
        self.setProperty('themeApplied', True)

@pytest.fixture()
def setup_theme_bus(qtbot):
    bus = EventBus()
    services.register('event_bus', bus, allow_override=True)
    theme = ThemeService.create_default()
    services.register('theme_service', theme, allow_override=True)
    # Minimal faux MainWindow substitute: just supply children and handler
    class FauxRoot(DemoLabel):
        pass
    root = FauxRoot()
    qtbot.addWidget(root)
    # Simulate subscription like MainWindow would
    bus.subscribe(GUIEvent.THEME_CHANGED, lambda evt: root.on_theme_changed(theme, evt.payload.get('changed', [])))
    return bus, theme, root


def test_theme_propagation_invokes_children(setup_theme_bus):
    bus, theme, root = setup_theme_bus
    # Trigger a theme variant change
    diff = theme.set_variant('high-contrast')
    assert not diff.no_changes
    # The change should have emitted an event -> incrementing called
    assert root.called >= 1
    assert isinstance(root.last_changed, tuple)

