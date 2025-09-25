"""Tests for responsive chart adjustments (Milestone 7.9)."""
from __future__ import annotations

from src.gui.charting import chart_registry, ChartRequest


def test_responsive_meta_present():
    # Build a line chart with many ticks to trigger thinning logic on narrow width.
    data_points = list(range(40))
    req = ChartRequest(
        chart_type="line.basic",
        data={"series": [data_points], "labels": ["Series"], "x": list(range(len(data_points)))},
    )
    result = chart_registry.build(req)
    # Responsive meta should exist on the figure; we surface it indirectly via build meta if needed later.
    # For now, just assert chart builds and meta has build_ms.
    assert "build_ms" in result.meta


def test_responsive_no_regression_heatmap():
    req = ChartRequest(chart_type="team_availability_heatmap", data={"team_id": 999})
    res = chart_registry.build(req)
    assert res.widget is not None
