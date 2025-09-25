"""Tests for snapshot caching (Milestone 7.10)."""
from __future__ import annotations

from src.gui.charting import chart_registry, ChartRequest


def test_snapshot_cache_hit():
    req = ChartRequest(chart_type="line.basic", data={"series": [[1, 2, 3]], "labels": ["L"], "x": [0, 1, 2]})
    first = chart_registry.build_cached(req)
    assert first.meta.get("cache_hit") is False
    second = chart_registry.build_cached(req)
    assert second.meta.get("cache_hit") is True
    # widgets should be identical object (snapshot reuse)
    assert first.widget is second.widget


def test_snapshot_cache_independent_requests():
    req1 = ChartRequest(chart_type="line.basic", data={"series": [[1, 2]], "labels": ["A"], "x": [0, 1]})
    req2 = ChartRequest(chart_type="line.basic", data={"series": [[2, 3]], "labels": ["B"], "x": [0, 1]})
    r1 = chart_registry.build_cached(req1)
    r2 = chart_registry.build_cached(req2)
    assert r1.widget is not r2.widget
    assert r1.meta.get("cache_hit") is False
    assert r2.meta.get("cache_hit") is False
