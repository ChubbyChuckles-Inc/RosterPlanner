"""Tests for chart registry and basic line chart (Milestone 7.1)."""

from __future__ import annotations

import pytest

from gui.charting import chart_registry, ChartRequest
from gui.charting.registry import register_chart_plugin


def test_register_duplicate_chart_type():
    from gui.charting.registry import register_chart_type

    def _dummy(req, backend):  # pragma: no cover - simple stub
        from gui.charting.types import ChartResult

        return ChartResult(widget=None, meta={})

    # register unique type
    unique_type = "custom.unique"
    register_chart_type(unique_type, _dummy, "Unique")
    # duplicate should raise
    with pytest.raises(ValueError):
        register_chart_type(unique_type, _dummy, "Duplicate")


def test_basic_line_chart_build():
    req = ChartRequest(
        chart_type="line.basic",
        data={"series": [[1, 2, 3], [3, 2, 1]], "labels": ["A", "B"], "x": [0, 1, 2]},
        options={"title": "Demo"},
    )
    result = chart_registry.build(req)
    assert result.meta["series_count"] == 2
    # Widget presence (in headless CI matplotlib canvas may still be object)
    assert result.widget is not None


def test_unknown_chart_type():
    req = ChartRequest(chart_type="unknown.type", data={})
    with pytest.raises(KeyError):
        chart_registry.build(req)


def test_basic_line_chart_input_validation():
    # Non-dict data
    bad_req = ChartRequest(chart_type="line.basic", data=[1, 2, 3])
    with pytest.raises(TypeError):
        chart_registry.build(bad_req)
    # Missing series
    bad_req2 = ChartRequest(chart_type="line.basic", data={})
    with pytest.raises(ValueError):
        chart_registry.build(bad_req2)


def test_plugin_registration_and_listing():
    class SamplePlugin:
        id = "sample.plugin"
        version = "1.0.0"

        def register(self, registrar):  # pragma: no cover - trivial wrapper
            def _builder(req, backend):
                from gui.charting.types import ChartResult

                return ChartResult(widget=None, meta={"ok": True})

            registrar.register(
                "sample.custom",
                _builder,
                "Sample Custom Chart",
                capability="demo",
            )

    plugin = SamplePlugin()
    register_chart_plugin(plugin)
    # Plugin listed
    plugins = chart_registry.list_plugins()
    assert plugin.id in plugins and plugins[plugin.id] == plugin.version
    # Type accessible via plugin listing
    types = chart_registry.list_types_by_plugin(plugin.id)
    assert "sample.custom" in types
    # Build chart from plugin
    result = chart_registry.build(ChartRequest(chart_type="sample.custom", data={"series": [[1]]}))
    assert result.meta["ok"] is True


def test_duplicate_plugin_registration_rejected():
    class DupPlugin:
        id = "dup.plugin"
        version = "0.1"

        def register(self, registrar):  # pragma: no cover
            def _builder(req, backend):
                from gui.charting.types import ChartResult

                return ChartResult(widget=None, meta={})

            registrar.register("dup.chart", _builder, "Dup")

    p = DupPlugin()
    register_chart_plugin(p)
    with pytest.raises(ValueError):
        register_chart_plugin(p)
