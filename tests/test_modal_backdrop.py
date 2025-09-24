"""Tests for ModalBackdrop (Milestone 5.10.66)."""

from __future__ import annotations

from PyQt6.QtWidgets import QApplication, QWidget, QLabel

from src.gui.components.modal_backdrop import ModalBackdrop
from src.gui.design import reduced_motion


_APP = None


def _ensure_app():
    global _APP
    app = QApplication.instance()
    if app is None:
        _APP = QApplication([])
    else:
        _APP = app


def test_backdrop_basic_show_and_dismiss(qtbot):
    _ensure_app()
    parent = QWidget()
    parent.resize(400, 300)
    parent.show()
    qtbot.addWidget(parent)
    content = QLabel("Dialog Body")
    backdrop = ModalBackdrop(parent)
    backdrop.show_with_content(content)
    assert backdrop.is_active()
    assert content.isVisible()
    backdrop.dismiss()
    assert not backdrop.is_active()


def test_backdrop_reduced_motion_skips_zoom(qtbot):
    _ensure_app()
    parent = QWidget()
    parent.resize(300, 200)
    parent.show()
    qtbot.addWidget(parent)
    content = QLabel("Body")
    reduced_motion.set_reduced_motion(True)
    try:
        backdrop = ModalBackdrop(parent)
        backdrop.show_with_content(content)
        # In reduced motion, opacity should already be final and no zoom animation
        assert backdrop._zoom_anim is None  # type: ignore[attr-defined]
        assert backdrop._opacity == 1.0  # type: ignore[attr-defined]
    finally:
        reduced_motion.set_reduced_motion(False)
