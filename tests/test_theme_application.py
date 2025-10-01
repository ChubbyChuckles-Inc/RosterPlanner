import os
from PyQt6.QtWidgets import QApplication, QWidget
from PyQt6.QtCore import Qt

# Ensure Qt runs headless during tests
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
os.environ.setdefault("RP_TEST_MODE", "1")

app = QApplication.instance() or QApplication([])


class _FakeTheme:
    def __init__(self):
        self._colors = {
            "surface.dialog": "#182030",
            "surface.card": "#1E2735",
            "background.secondary": "#202B3A",
            "background.primary": "#121820",
            "titlebar.background": "#1A2330",
            "titlebar.border": "#2C3A52",
            "statusbar.background": "#141D29",
            "statusbar.border": "#2E3C54",
            "border.medium": "#2E3C54",
            "accent.base": "#4C8EF7",
            "text.primary": "#F5F7FA",
            "text.muted": "#B6C2D4",
            "state.error.bg": "#C0392B",
            "state.error.fg": "#FFFFFF",
        }

    def colors(self):
        return dict(self._colors)

    def generate_qss(self):
        return ""  # minimal stub for calls expecting method


def test_chrome_dialog_applies_theme(qtbot):
    from gui.components.chrome_dialog import ChromeDialog
    from gui.services.service_locator import services

    with services.override_context(theme_service=_FakeTheme()):
        dialog = ChromeDialog(title="Theme Test")
        qtbot.addWidget(dialog)
        dialog.show()
        qtbot.wait(10)

        title_bar = dialog.findChild(QWidget, "chromeTitleBar")
        assert title_bar is not None
        assert "#1A2330" in (title_bar.styleSheet() or "")
        assert title_bar.testAttribute(Qt.WidgetAttribute.WA_StyledBackground)

        content = dialog.findChild(QWidget, "chromeContentHost")
        assert content is not None
        assert "#182030" in (content.styleSheet() or "")
        assert content.testAttribute(Qt.WidgetAttribute.WA_StyledBackground)

        dialog.close()


def test_main_window_status_bar_uses_theme(qtbot, tmp_path):
    from gui.views.main_window import MainWindow
    from gui.services.service_locator import services

    with services.override_context(theme_service=_FakeTheme()):
        window = MainWindow(club_id=1, season=2025, data_dir=str(tmp_path))
        qtbot.addWidget(window)
        status_bar = window.statusBar()
        assert status_bar is not None
        style = status_bar.styleSheet()
        assert "#141D29" in style
        widget = getattr(window, "_status_bar_widget", None)
        assert widget is not None
        assert "#141D29" in (widget.styleSheet() or "")
        window.close()
