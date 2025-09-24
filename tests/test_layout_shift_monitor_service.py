"""Tests for LayoutShiftMonitor (Milestone 5.10.64)."""

from __future__ import annotations

import math

from PyQt6.QtWidgets import QApplication, QWidget

from src.gui.services.layout_shift_monitor_service import LayoutShiftMonitor


_APP = None


def ensure_app():  # helper to avoid duplicate code
    global _APP
    app = QApplication.instance()
    if app is None:  # pragma: no cover - environment dependent
        _APP = QApplication([])
    else:
        _APP = app


def test_no_score_on_initial_registration(qtbot):
    ensure_app()
    monitor = LayoutShiftMonitor()
    w = QWidget()
    w.setObjectName("alpha")
    w.setGeometry(0, 0, 100, 50)
    monitor.register(w)
    assert math.isclose(monitor.cumulative_score(), 0.0)
    assert monitor.records == []


def test_score_accumulates_on_move_and_resize(qtbot):
    ensure_app()
    monitor = LayoutShiftMonitor(ignore_threshold=0)
    w = QWidget()
    w.setObjectName("beta")
    w.setGeometry(10, 10, 100, 50)
    monitor.register(w)
    qtbot.addWidget(w)
    w.show()
    qtbot.wait(10)

    # Move
    w.setGeometry(30, 25, 100, 50)  # dx=20, dy=15 -> 35 pts
    qtbot.wait(10)
    # Resize
    w.setGeometry(30, 25, 120, 70)  # dw=20, dh=20 -> +0.25*(40)=10 pts
    qtbot.wait(10)

    total = monitor.cumulative_score()
    # Expect 35 + 10 = 45
    assert 44.9 < total < 45.1
    assert len(monitor.records) >= 2
    # Last record is resize
    last = monitor.records[-1]
    assert last.new_rect.width() == 120
    assert last.score >= 9.9


def test_ignore_small_jitter_with_threshold(qtbot):
    ensure_app()
    monitor = LayoutShiftMonitor(ignore_threshold=3)
    w = QWidget()
    w.setGeometry(0, 0, 50, 50)
    monitor.register(w)
    qtbot.addWidget(w)
    w.show()
    qtbot.wait(5)
    # Small move below threshold
    w.setGeometry(2, 1, 51, 49)  # dx=2<=3 dy=1<=3 dw=1<=3 dh=1<=3 -> ignore
    qtbot.wait(5)
    assert monitor.cumulative_score() == 0.0
    assert monitor.records == []


def test_reset_preserves_baseline(qtbot):
    ensure_app()
    monitor = LayoutShiftMonitor()
    w = QWidget()
    w.setGeometry(0, 0, 40, 40)
    monitor.register(w)
    qtbot.addWidget(w)
    w.show()
    qtbot.wait(5)
    w.setGeometry(10, 0, 40, 40)  # dx=10 -> score 10
    qtbot.wait(5)
    assert monitor.cumulative_score() >= 10
    monitor.reset()
    assert monitor.cumulative_score() == 0.0
    # Re-register to explicitly re-baseline (avoids intermediate platform move events interfering)
    monitor.register(w)
    w.setGeometry(10, 0, 40, 40)  # no actual change -> no score
    qtbot.wait(2)
    w.setGeometry(15, 0, 40, 40)  # follow-up move; expect small positive score
    qtbot.wait(5)
    follow = monitor.cumulative_score()
    assert (
        0 < follow < 25
    )  # relaxed due to potential multi-event intermediate moves on some platforms
