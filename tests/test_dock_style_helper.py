import sys
import pytest

try:  # pragma: no cover
    from PyQt6.QtWidgets import QApplication, QDockWidget, QWidget
except Exception:  # pragma: no cover
    QApplication = None  # type: ignore

from gui.services.dock_style import DockStyleHelper


@pytest.mark.skipif(QApplication is None, reason="PyQt6 not available")
def test_create_title_bar_applies_custom_widget(qtbot):  # requires pytest-qt
    if QApplication.instance() is None:
        _app = QApplication(sys.argv)  # noqa: F841
    dock = QDockWidget("Test Dock")
    qtbot.addWidget(dock)  # type: ignore
    helper = DockStyleHelper()
    helper.create_title_bar(dock)
    tb = dock.titleBarWidget()
    assert tb is not None
    # Ensure grip label was added (object name for label)
    labels = tb.findChildren(QWidget)
    assert any(getattr(w, "objectName", lambda: "")() == "DockTitleLabel" for w in labels)
