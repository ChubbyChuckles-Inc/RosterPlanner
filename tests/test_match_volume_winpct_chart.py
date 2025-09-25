"""Tests for match volume & cumulative win % chart (Milestone 7.6).

Validates registration and graceful empty behavior when schema/data is absent.
Further enhancements can inject synthetic matches to assert series math.
"""

from __future__ import annotations

from src.gui.charting import chart_registry, ChartRequest


def test_match_volume_winpct_registered():
    assert "team.match_volume_winpct" in chart_registry.list_types()


def test_match_volume_winpct_empty_without_schema():
    req = ChartRequest(chart_type="team.match_volume_winpct", data={"team_id": 42})
    result = chart_registry.build(req)
    assert result.meta.get("status") in {"empty", "ok"}
    assert result.widget is not None


def test_match_volume_winpct_requires_team_id():
    from pytest import raises

    with raises(ValueError):
        chart_registry.build(ChartRequest(chart_type="team.match_volume_winpct", data={}))
