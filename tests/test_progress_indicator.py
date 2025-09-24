"""Tests for Progress Indicators (Milestone 5.10.67)."""

from __future__ import annotations
from PyQt6.QtWidgets import QApplication, QWidget
from time import sleep

from src.gui.components.progress_indicator import DeterminateProgress, IndeterminateProgress
from src.gui.design import reduced_motion

_APP = None


def _ensure_app():
    global _APP
    app = QApplication.instance()
    if app is None:
        _APP = QApplication([])
    else:
        _APP = app


def test_determinate_progress_basic(qtbot):
    _ensure_app()
    w = DeterminateProgress()
    qtbot.addWidget(w)
    assert w.progress() == 0.0
    w.set_progress(0.5)
    assert 0.49 < w.progress() < 0.51
    w.set_progress(2.0)  # clamp
    assert w.progress() == 1.0


def test_indeterminate_respects_reduced_motion(qtbot):
    _ensure_app()
    reduced_motion.set_reduced_motion(True)
    try:
        w = IndeterminateProgress()
        qtbot.addWidget(w)
        w.start()
        assert not w.is_active()  # animation disabled
        phase_before = w.debug_phase()
        # simulate waiting; phase should not change
        sleep(0.05)
        assert w.debug_phase() == phase_before
    finally:
        reduced_motion.set_reduced_motion(False)


def test_indeterminate_animates(qtbot):
    _ensure_app()
    w = IndeterminateProgress(interval_ms=10)
    qtbot.addWidget(w)
    w.start()
    # Allow a few ticks
    sleep(0.05)
    phase = w.debug_phase()
    assert phase > 0.0
    w.stop()
    assert not w.is_active()
