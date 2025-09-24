"""Tests for StatusBarWidget (Milestone 5.10.59)."""

from __future__ import annotations
from PyQt6.QtWidgets import QApplication
from gui.components.status_bar import StatusBarWidget, _sparkline


def test_sparkline_basic():
    assert _sparkline([]) == "-"
    assert _sparkline([1, 1, 1])  # uniform -> repeated mid char
    s = _sparkline([0, 4, 8])
    assert len(s) == 3


def test_status_bar_updates(monkeypatch):
    app = QApplication.instance() or QApplication([])
    sb = StatusBarWidget()
    sb.update_message("Hello")
    assert sb.lbl_message.text() == "Hello"
    sb.update_freshness("Fresh: now")
    assert "Fresh:" in sb.lbl_freshness.text()
    sb.update_trend([0, 1, 2, 3])
    assert sb.lbl_trend.text() != ""
    sb.update_trend(None)
    assert not sb.lbl_trend.isVisible()
