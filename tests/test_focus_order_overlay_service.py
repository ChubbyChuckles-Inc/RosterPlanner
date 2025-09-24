"""Tests for FocusOrderOverlayService (Milestone 5.10.65)."""

from __future__ import annotations

from PyQt6.QtWidgets import QApplication, QWidget, QLineEdit, QPushButton, QVBoxLayout

from src.gui.services.focus_order_overlay_service import (
    compute_focus_order,
    FocusOrderOverlayService,
)


def _build_sample() -> QWidget:
    root = QWidget()
    layout = QVBoxLayout(root)
    a = QLineEdit()
    a.setObjectName("a_line")
    b = QPushButton("B")
    b.setObjectName("b_btn")
    c = QLineEdit()
    c.setObjectName("c_line")
    layout.addWidget(a)
    layout.addWidget(b)
    layout.addWidget(c)
    root.show()
    return root


_APP = None


def _ensure_app():
    global _APP
    app = QApplication.instance()
    if app is None:
        _APP = QApplication([])
    else:
        _APP = app


def test_compute_focus_order_basic(qtbot):
    _ensure_app()
    root = _build_sample()
    qtbot.addWidget(root)
    qtbot.wait(10)
    order = compute_focus_order(root)
    # Expect 3 focusable widgets in visual order (a, b, c)
    names = [w.objectName() for w in order]
    assert names == ["a_line", "b_btn", "c_line"]


def test_overlay_toggle_and_refresh(qtbot):
    _ensure_app()
    root = _build_sample()
    qtbot.addWidget(root)
    svc = FocusOrderOverlayService()
    svc.toggle(root)
    assert svc.is_visible()
    # Modify layout: swap order by reparenting last to top
    children = root.findChildren(QWidget)
    last_line = [w for w in children if w.objectName() == "c_line"][0]
    last_line.setParent(None)
    last_line.setParent(root)
    # Force refresh
    svc.refresh()
    assert svc.is_visible()
    svc.toggle(root)  # hide
    assert not svc.is_visible()
