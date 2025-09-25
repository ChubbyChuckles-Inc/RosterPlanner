"""Tests for chart registry and basic line chart (Milestone 7.1)."""
from __future__ import annotations

import pytest

from gui.charting import chart_registry, ChartRequest


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
        data={"series": [[1,2,3],[3,2,1]], "labels": ["A","B"], "x": [0,1,2]},
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
    bad_req = ChartRequest(chart_type="line.basic", data=[1,2,3])
    with pytest.raises(TypeError):
        chart_registry.build(bad_req)
    # Missing series
    bad_req2 = ChartRequest(chart_type="line.basic", data={})
    with pytest.raises(ValueError):
        chart_registry.build(bad_req2)
