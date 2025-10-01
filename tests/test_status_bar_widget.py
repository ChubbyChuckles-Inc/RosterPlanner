"""Tests for StatusBarWidget (Milestone 5.10.59)."""

from __future__ import annotations
from PyQt6.QtWidgets import QApplication
from gui.components.status_bar import StatusBarWidget, _sparkline
from gui.services.theme_service import ThemeService


def test_sparkline_basic():
    assert _sparkline([]) == "-"
    assert _sparkline([1, 1, 1])  # uniform -> repeated mid char
    s = _sparkline([0, 4, 8])
    assert len(s) == 3


def test_status_bar_updates(monkeypatch, qtbot):
    app = QApplication.instance() or QApplication([])
    sb = StatusBarWidget()
    qtbot.addWidget(sb)  # type: ignore[arg-type]
    sb.update_message("Hello")
    assert sb.lbl_message.text() == "Hello"
    sb.update_freshness("Fresh: now")
    assert "Fresh:" in sb.lbl_freshness.text()
    sb.update_trend([0, 1, 2, 3])
    assert sb.lbl_trend.text() != ""
    sb.update_trend(None)
    assert not sb.lbl_trend.isVisible()
    # Diagnostics badges
    sb.update_diagnostics(0, 0)
    assert not sb.lbl_warn.isVisible() and not sb.lbl_error.isVisible()
    sb.update_diagnostics(2, 1)
    assert "⚠ 2" in sb.lbl_warn.text()
    assert "⛔ 1" in sb.lbl_error.text()


def test_status_bar_theme_applies(qtbot):
    app = QApplication.instance() or QApplication([])
    sb = StatusBarWidget()
    qtbot.addWidget(sb)  # type: ignore[arg-type]
    svc = ThemeService.create_default()
    sb.on_theme_changed(svc, [])
    style = sb.styleSheet()
    colors = svc.colors()
    expected_bg = colors.get("statusbar.background", colors.get("background.secondary"))
    assert expected_bg is None or expected_bg in style
