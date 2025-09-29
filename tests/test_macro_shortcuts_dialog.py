import os
from PyQt6.QtWidgets import QApplication

# Ensure headless friendly environment for Qt dialogs
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
os.environ.setdefault("RP_TEST_MODE", "1")

app = QApplication.instance() or QApplication([])


def test_macro_shortcut_dialog_uses_chrome_content_layout(qtbot):
    from gui.ingestion.macro_shortcuts import MacroShortcutDialog, MacroShortcutTemplate

    stored = [
        MacroShortcutTemplate(
            name="Trim Sample",
            chain=[{"kind": "trim"}],
            sequence="Ctrl+Shift+T",
            source="custom",
            description="Simple trim chain",
        )
    ]

    dialog = MacroShortcutDialog(stored, suggestions=None)
    qtbot.addWidget(dialog)

    layout = dialog.content_layout()
    assert layout.count() > 0, "Expected ChromeDialog content layout to host dialog widgets"

    dialog.close()
