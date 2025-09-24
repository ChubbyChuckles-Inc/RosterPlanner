"""Smoke test for custom window chrome (Milestone 5.10.57).

Ensures that enabling the feature flag does not crash window initialization
and that the central DocumentArea remains accessible.

This is intentionally lightweight: we do not assert on pixel geometry or
native frame removal (platform dependent), only object wiring.
"""

from __future__ import annotations
import os
import pytest

from PyQt6.QtWidgets import QApplication, QMainWindow, QWidget
from gui.services.window_chrome import try_enable_custom_chrome


@pytest.fixture
def app():
    app = QApplication.instance() or QApplication([])
    return app


def test_custom_chrome_init_smoke(app, monkeypatch):
    monkeypatch.setenv("ENABLE_CUSTOM_CHROME", "1")
    # Use lightweight QMainWindow to avoid side effects of full MainWindow boot
    win = QMainWindow()
    placeholder = QWidget()
    win.setCentralWidget(placeholder)
    try_enable_custom_chrome(win)
    # After applying custom chrome, the central widget should be replaced by chrome container
    chrome_widget = win.centralWidget()
    assert chrome_widget is not None
    # The original placeholder should now have new parent (content_host)
    assert placeholder.parent() is not None
    # Ensure window flags include FramelessWindowHint when feature flag active
    from PyQt6.QtCore import Qt

    assert bool(win.windowFlags() & Qt.WindowType.FramelessWindowHint)
    win.close()
