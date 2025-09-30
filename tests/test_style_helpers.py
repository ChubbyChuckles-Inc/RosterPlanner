from __future__ import annotations

from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import QApplication, QWidget

from gui.utils.style_helpers import ensure_styled_background


def test_ensure_styled_background_sets_flags():
    app = QApplication.instance() or QApplication([])
    _ = app
    widget = QWidget()
    widget.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, False)
    widget.setAutoFillBackground(False)

    ensure_styled_background(widget)

    assert widget.testAttribute(Qt.WidgetAttribute.WA_StyledBackground)
    assert widget.autoFillBackground()
