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
    btn.show()
    install_focus_ring(btn)
    btn.setFocus()
    from PyQt6.QtCore import QCoreApplication

    for _ in range(5):
        QCoreApplication.processEvents()
        qtbot.wait(5)
    assert btn.property("a11yFocused") == "true"
    btn.clearFocus()
    for _ in range(5):
        QCoreApplication.processEvents()
        qtbot.wait(5)
    assert btn.property("a11yFocused") == "false"
