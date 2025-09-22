from gui.design.icon_registry import IconRegistry, get_icon
from PyQt6.QtWidgets import QApplication
import sys


def test_refresh_icon_discovered():
    app = QApplication.instance() or QApplication(sys.argv[:1])
    reg = IconRegistry.instance()
    assert "refresh" in reg.list_icons()
    icon = get_icon("refresh", size=16)
    assert icon is not None
    # color variant caching
    icon_colored = get_icon("refresh", size=16, color="#ff0000")
    assert icon_colored is not None


def test_unknown_icon_returns_none():
    app = QApplication.instance() or QApplication(sys.argv[:1])
    assert get_icon("not-present", size=16) is None


def test_additional_builtin_icons():
    app = QApplication.instance() or QApplication(sys.argv[:1])
    reg = IconRegistry.instance()
    # Ensure newly added ones are discovered
    for name in ["save", "folder-open"]:
        assert name in reg.list_icons()
        assert get_icon(name, size=12) is not None
