import sys
import pytest

try:  # pragma: no cover
    from PyQt6.QtWidgets import QApplication
except Exception:  # pragma: no cover
    QApplication = None  # type: ignore

from gui.services.shortcut_registry import global_shortcut_registry

if QApplication is not None:  # pragma: no cover
    from gui.views.shortcut_cheatsheet import ShortcutCheatSheetDialog


@pytest.mark.skipif(QApplication is None, reason="PyQt6 not available")
def test_cheatsheet_populates_and_filters(qtbot):  # requires pytest-qt
    if QApplication.instance() is None:
        _app = QApplication(sys.argv)  # noqa: F841
    # Ensure at least two shortcuts
    global_shortcut_registry.register(
        "dialog.openPalette", "Ctrl+P", "Open Palette", category="Navigation"
    )
    global_shortcut_registry.register(
        "dialog.openShortcuts", "Ctrl+K", "Open Shortcuts", category="Help"
    )
    dlg = ShortcutCheatSheetDialog()
    qtbot.addWidget(dlg)  # type: ignore
    # Initially both should show
    assert dlg.tree.topLevelItemCount() >= 2
    # Filter by 'palette'
    dlg.filter_edit.setText("palette")
    assert dlg.tree.topLevelItemCount() == 1
