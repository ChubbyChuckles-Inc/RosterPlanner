import sys
import pytest

try:
    from PyQt6.QtWidgets import QApplication
except Exception:  # pragma: no cover
    QApplication = None  # type: ignore

from gui.services.command_registry import global_command_registry

# Only import dialog if PyQt available
if QApplication is not None:  # pragma: no cover
    from gui.views.command_palette import CommandPaletteDialog


@pytest.mark.skipif(QApplication is None, reason="PyQt6 not available")
def test_palette_populates_and_filters(qtbot):  # requires pytest-qt if available
    if QApplication.instance() is None:
        _app = QApplication(sys.argv)  # noqa: F841
    # Register sample commands (ensure clean slate by creating a local set)
    try:
        global_command_registry.reset()  # type: ignore[attr-defined]
    except Exception:
        pass
    global_command_registry.register("sample.one", "Sample One", lambda: None)
    global_command_registry.register("sample.two", "Second Sample", lambda: None)
    dlg = CommandPaletteDialog()
    qtbot.addWidget(dlg)  # type: ignore
    dlg._refresh_list("")
    assert dlg.list_widget.count() >= 2
    # Filter down
    dlg._refresh_list("two")
    assert dlg.list_widget.count() == 1
    item_text = dlg.list_widget.item(0).text().lower()
    assert "second" in item_text or "two" in item_text
