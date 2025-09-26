import sys
import pytest

try:
    from PyQt6.QtWidgets import QApplication
except Exception:  # pragma: no cover
    QApplication = None  # type: ignore

from gui.services.command_registry import global_command_registry
from gui.services.settings_service import SettingsService

if QApplication is not None:  # pragma: no cover
    from gui.views.command_palette import CommandPaletteDialog


@pytest.mark.skipif(QApplication is None, reason="PyQt6 not available")
def test_command_palette_grows_for_long_command(qtbot):  # type: ignore
    if QApplication.instance() is None:
        _app = QApplication(sys.argv)  # noqa: F841
    # Ensure auto-resize enabled
    SettingsService.instance.command_palette_auto_resize = True
    global_command_registry.reset()  # type: ignore[attr-defined]
    global_command_registry.register("short.cmd", "Short", lambda: None)
    dlg = CommandPaletteDialog()
    qtbot.addWidget(dlg)  # type: ignore
    dlg._refresh_list("")
    w_initial = dlg.width()
    # Register a very long command and refresh
    long_title = "This Is An Exceptionally Long Command Title To Trigger Width Expansion"
    global_command_registry.register("long.cmd", long_title, lambda: None)
    dlg._refresh_list("")
    assert dlg.width() >= w_initial, "Dialog did not grow for longer command"


@pytest.mark.skipif(QApplication is None, reason="PyQt6 not available")
def test_command_palette_no_resize_when_disabled(qtbot):  # type: ignore
    if QApplication.instance() is None:
        _app = QApplication(sys.argv)  # noqa: F841
    SettingsService.instance.command_palette_auto_resize = False
    global_command_registry.reset()  # type: ignore[attr-defined]
    global_command_registry.register("short.cmd", "Short", lambda: None)
    dlg = CommandPaletteDialog()
    qtbot.addWidget(dlg)  # type: ignore
    dlg._refresh_list("")
    w_initial = dlg.width()
    # Add long command but auto-resize disabled
    long_title = "Another Extremely Long Command Title That Should Not Change Width"
    global_command_registry.register("long.cmd", long_title, lambda: None)
    dlg._refresh_list("")
    assert dlg.width() == w_initial, "Dialog width changed despite auto-resize disabled"
    # Re-enable for other tests
    SettingsService.instance.command_palette_auto_resize = True
