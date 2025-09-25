"""Tests for chart export & tooltip utilities (Milestone 7.7 partial).

Since we operate in a (likely) headless environment, we only verify that:
- export_chart writes a file for a simple line chart (PNG)
- enable_line_chart_tooltips does not raise (no functional hover test here)

Interactive hover behavior is not easily testable without a GUI loop;
we keep this lightweight until GUI integration tests are added.
"""

from __future__ import annotations

import os
import tempfile

from src.gui.charting import chart_registry, ChartRequest
from src.gui.charting.export import export_chart, enable_line_chart_tooltips


def _build_simple_chart():
    req = ChartRequest(
        chart_type="line.basic",
        data={"series": [[0, 1, 2], [1, 1, 1]], "labels": ["A", "B"], "x": [0, 1, 2]},
        options={"title": "Test"},
    )
    return chart_registry.build(req)


def test_export_chart_png(tmp_path):
    result = _build_simple_chart()
    out = tmp_path / "chart.png"
    export_chart(result.widget, str(out), format="png", dpi=90)
    assert out.exists() and out.stat().st_size > 0


def test_export_chart_svg(tmp_path):
    result = _build_simple_chart()
    out = tmp_path / "chart.svg"
    export_chart(result.widget, str(out), format="svg")
    assert out.exists() and out.stat().st_size > 0


def test_enable_tooltips_no_error():
    result = _build_simple_chart()
    enable_line_chart_tooltips(
        result.widget, [[0, 1, 2], [1, 1, 1]], [0, 1, 2], ["A", "B"]
    )  # should not raise
