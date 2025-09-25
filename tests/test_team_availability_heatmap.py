"""Tests for provisional team availability heatmap chart (Milestone 7.4).

Because the underlying match participation / team roster tables may not
exist yet in the test database, we validate graceful degradation: the chart
returns an "empty" metadata status and still yields a widget object.

Once schema exists these tests can be extended to insert synthetic rows
and assert matrix mapping.
"""

from __future__ import annotations

import pytest

from src.gui.charting import chart_registry, ChartRequest


def test_team_availability_heatmap_registered():
    assert (
        "team_availability_heatmap" in chart_registry.list_types().keys()
    ), "Chart type should be registered"


def test_team_availability_heatmap_empty_when_no_schema():
    # For consistency with other charts, we pass params via the data dict.
    req = ChartRequest(chart_type="team_availability_heatmap", data={"team_id": 9999})
    result = chart_registry.build(req)
    assert result.meta.get("status") in {"empty", "ok"}
    # Widget existence (cannot assert more without GUI harness)
    assert result.widget is not None


def test_team_availability_heatmap_requires_team_id():
    with pytest.raises(ValueError):
        chart_registry.build(ChartRequest(chart_type="team_availability_heatmap", data={}))
