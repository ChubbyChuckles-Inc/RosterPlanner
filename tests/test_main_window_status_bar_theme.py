import os
import sys
import pytest

try:  # pragma: no cover
    from PyQt6.QtWidgets import QApplication, QStatusBar
    from PyQt6.QtCore import Qt
except Exception:  # pragma: no cover
    QApplication = None  # type: ignore

from gui.views.main_window import MainWindow

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")


@pytest.mark.skipif(QApplication is None, reason="PyQt6 not available")
def test_status_bar_applies_theme_colors(qtbot):
    if QApplication.instance() is None:
        _app = QApplication(sys.argv)  # noqa: F841

    class _StubTheme:
        def colors(self):
            return {
                "statusbar.background": "#111111",
                "statusbar.border": "#222222",
                "text.primary": "#eeeeee",
                "text.muted": "#bbbbbb",
            }

    theme = _StubTheme()
    status_bar = QStatusBar()
    status_bar.setObjectName("MainStatusBar")
    qtbot.addWidget(status_bar)  # type: ignore

    class _Harness:
        def __init__(self, sb):
            self._status_bar = sb

    harness = _Harness(status_bar)
    MainWindow._apply_status_bar_theme(harness, theme)

    assert status_bar.objectName() == "MainStatusBar"
    assert status_bar.testAttribute(Qt.WidgetAttribute.WA_StyledBackground)
    style = status_bar.styleSheet()
    assert "#111111" in style
    assert "#222222" in style
    assert "#eeeeee" in style
    assert "#bbbbbb" in style
