"""Tests for ThemeWarmLoader (Milestone 5.10.69)."""

from __future__ import annotations
from PyQt6.QtWidgets import QApplication

from src.gui.services.theme_warm_loader import ThemeWarmLoader
from src.gui.design.theme_manager import ThemeManager
from gui.design.loader import load_tokens  # reuse tokens loader (may be available via src path too)

_APP = None


def _ensure_app():
    global _APP
    app = QApplication.instance()
    if app is None:
        _APP = QApplication([])
    else:
        _APP = app


def test_warm_loader_prefetches_accent_palettes():
    _ensure_app()
    tokens = load_tokens()
    tm = ThemeManager(tokens)
    base = tm.accent_base.upper()
    seeds = [base, "#FF5733", "#198754"]
    loader = ThemeWarmLoader(tm, delay_ms=0, accent_seeds=seeds)
    assert loader.is_completed()
    cache = getattr(tm, "_accent_cache")
    for s in seeds:
        assert s.upper() in cache


def test_warm_loader_run_now():
    _ensure_app()
    tokens = load_tokens()
    tm = ThemeManager(tokens)
    seeds = [tm.accent_base, "#6610F2"]
    loader = ThemeWarmLoader(tm, delay_ms=200, accent_seeds=seeds)
    assert not loader.is_completed()
    loader.run_now()
    assert loader.is_completed()
    cache = getattr(tm, "_accent_cache")
    for s in seeds:
        assert s.upper() in cache
