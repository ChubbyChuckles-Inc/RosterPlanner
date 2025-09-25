"""Tests for lazy chart building & build timing (Milestone 7.8 partial)."""
from __future__ import annotations

from src.gui.charting import chart_registry, ChartRequest


def test_lazy_proxy_defers_build(monkeypatch):
    calls = {"count": 0}

    # Register a temporary chart type
    def _builder(req, backend):  # noqa: D401
        calls["count"] += 1
        w = backend.create_line_chart([[0, 1]], labels=["A"], title=None)
        from src.gui.charting.types import ChartResult
        return ChartResult(widget=w, meta={"ok": True})

    name = "test.lazy.temp"
    if name not in chart_registry.list_types():
        from src.gui.charting.registry import register_chart_type
        register_chart_type(name, _builder, "temp")

    req = ChartRequest(chart_type=name, data={"series": [[0, 1]], "labels": ["A"]})
    proxy = chart_registry.build_lazy(req)
    assert calls["count"] == 0  # not built yet
    _ = proxy.meta  # meta access doesn't build
    assert calls["count"] == 0
    _ = proxy.widget  # triggers build
    assert calls["count"] == 1
    # second access does not rebuild
    _ = proxy.widget
    assert calls["count"] == 1
    assert proxy.meta["lazy"] is True
    assert "build_ms" in proxy.meta


def test_eager_build_has_build_ms():
    req = ChartRequest(chart_type="line.basic", data={"series": [[1, 2, 3]], "labels": ["L"], "x": [0, 1, 2]})
    result = chart_registry.build(req)
    assert "build_ms" in result.meta
    assert result.meta["build_ms"] >= 0
