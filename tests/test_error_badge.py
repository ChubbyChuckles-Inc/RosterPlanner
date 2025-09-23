from gui.components.error_badge import ErrorBadge
from PyQt6.QtWidgets import QApplication
import sys


def test_error_badge_basic(qtbot):
    app = QApplication.instance() or QApplication(sys.argv)
    badge = ErrorBadge("ERR", severity="error")
    qtbot.addWidget(badge)
    assert badge.severity() == "error"
    bg1, fg1 = badge.palette_tuple()
    badge.set_severity("warning")
    assert badge.severity() == "warning"
    bg2, fg2 = badge.palette_tuple()
    assert (bg1, fg1) != (bg2, fg2)


def test_error_badge_invalid_severity_defaults(qtbot):
    app = QApplication.instance() or QApplication(sys.argv)
    badge = ErrorBadge("!", severity="not-a-severity")
    qtbot.addWidget(badge)
    assert badge.severity() == "error"  # fallback
