from gui.design.icon_registry import IconRegistry, get_icon
from PyQt6.QtWidgets import QApplication
import sys


def test_refresh_icon_discovered():
    app = QApplication.instance() or QApplication(sys.argv[:1])
    reg = IconRegistry.instance()
    assert "refresh" in reg.list_icons()
    icon = get_icon("refresh", size=16)
    assert icon is not None


def test_unknown_icon_returns_none():
    app = QApplication.instance() or QApplication(sys.argv[:1])
    assert get_icon("not-present", size=16) is None
