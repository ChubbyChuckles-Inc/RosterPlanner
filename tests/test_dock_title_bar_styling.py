import os
import sys
import pytest
from PyQt6.QtWidgets import QApplication, QDockWidget

from gui.services.dock_style import DockStyleHelper
from gui.services.theme_service import ThemeService

os.environ.setdefault('QT_QPA_PLATFORM','offscreen')

@pytest.mark.skipif(QApplication is None, reason="PyQt6 not available")
def test_dock_title_bar_has_object_names_and_updates(qtbot):
    if QApplication.instance() is None:
        _app = QApplication(sys.argv)  # noqa: F841
    dock = QDockWidget("Sample Dock")
    qtbot.addWidget(dock)  # type: ignore
    helper = DockStyleHelper()
    helper.create_title_bar(dock)
    tb = dock.titleBarWidget()
    assert tb is not None
    assert tb.objectName() == 'DockTitleBar'
    lbl = tb.findChild(type(dock), 'DockTitleLabel')
    # Because label is a QLabel, we can query via QObject findChildren generically
    from PyQt6.QtWidgets import QLabel
    label = tb.findChild(QLabel, 'DockTitleLabel')
    assert label is not None
    # Simulate hover enter/leave
    from PyQt6.QtCore import QEvent
    helper.eventFilter(tb, QEvent(QEvent.Type.Enter))
    assert tb.property('dockHover') is True
    helper.eventFilter(tb, QEvent(QEvent.Type.Leave))
    assert tb.property('dockHover') is False


def test_theme_service_qss_contains_dock_section():
    svc = ThemeService.create_default()
    qss = svc.generate_qss()
    assert 'Dock Title Bar Styling' in qss
    assert 'QDockWidget > QWidget#DockTitleBar' in qss
