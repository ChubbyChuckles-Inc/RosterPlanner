"""Tests for LayoutReflowCoordinator (Milestone 5.10.68)."""

from __future__ import annotations
from PyQt6.QtWidgets import QApplication, QWidget
from time import sleep

from src.gui.services.layout_reflow_coordinator import LayoutReflowCoordinator

_APP = None


def _ensure_app():
    global _APP
    app = QApplication.instance()
    if app is None:
        _APP = QApplication([])
    else:
        _APP = app


def test_single_callback_after_rapid_resizes(qtbot):
    _ensure_app()
    w = QWidget()
    w.resize(200, 100)
    w.show()
    qtbot.addWidget(w)
    hits = []
    coord = LayoutReflowCoordinator(debounce_ms=80)
    coord.watch(w, lambda size: hits.append((size.width(), size.height())))
    # Simulate rapid resizes
    for new_w in [210, 220, 230, 240]:
        w.resize(new_w, 100)
    # Not yet flushed
    assert coord.pending_count() == 1
    coord.force_commit()
    assert len(hits) == 1
    # Last size should be committed
    assert hits[0][0] == 240


def test_independent_widgets(qtbot):
    _ensure_app()
    a = QWidget()
    a.resize(100, 50)
    a.show()
    qtbot.addWidget(a)
    b = QWidget()
    b.resize(120, 60)
    b.show()
    qtbot.addWidget(b)
    hits_a = []
    hits_b = []
    coord = LayoutReflowCoordinator(debounce_ms=50)
    coord.watch(a, lambda size: hits_a.append(size.width()))
    coord.watch(b, lambda size: hits_b.append(size.width()))
    a.resize(150, 50)
    b.resize(170, 60)
    assert coord.pending_count() == 2
    coord.force_commit()
    assert hits_a == [150]
    assert hits_b == [170]


def test_force_commit_no_pending_is_safe(qtbot):
    _ensure_app()
    w = QWidget()
    w.resize(80, 40)
    w.show()
    qtbot.addWidget(w)
    coord = LayoutReflowCoordinator(debounce_ms=30)
    coord.watch(w, lambda size: None)
    # No resize yet
    assert coord.pending_count() == 0
    coord.force_commit()  # should be no-op
    assert coord.pending_count() == 0
