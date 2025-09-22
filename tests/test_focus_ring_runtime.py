import sys
import pytest

try:  # pragma: no cover
    from PyQt6.QtWidgets import QApplication, QPushButton
except Exception:  # pragma: no cover
    QApplication = None  # type: ignore

from gui.services.focus_style import install_focus_ring


@pytest.mark.skipif(QApplication is None, reason="PyQt6 not available")
def test_focus_ring_runtime_property(qtbot):  # requires pytest-qt
    if QApplication.instance() is None:
        _app = QApplication(sys.argv)  # noqa: F841
    btn = QPushButton("Focusable")
    qtbot.addWidget(btn)  # type: ignore
    install_focus_ring(btn)
    btn.setFocus()
    qtbot.wait(30)
    assert btn.property("a11yFocused") == "true"
    btn.clearFocus()
    qtbot.wait(30)
    assert btn.property("a11yFocused") == "false"
