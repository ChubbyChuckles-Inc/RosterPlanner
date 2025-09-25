"""Tests for division standings evolution chart (Milestone 7.5).

Since schema or data may be absent in the test environment, we assert
that the chart type is registered and returns an 'empty' status gracefully
when no division data is available. Later this can be expanded with
fixtures inserting synthetic teams and matches to validate the ordering
logic and evolution snapshots.
"""
from __future__ import annotations

from src.gui.charting import chart_registry, ChartRequest


def test_division_standings_evolution_registered():
    assert "division.standings.evolution" in chart_registry.list_types()


def test_division_standings_evolution_empty_without_schema():
    req = ChartRequest(chart_type="division.standings.evolution", data={"division_id": 12345})
    result = chart_registry.build(req)
    assert result.meta.get("status") in {"empty", "ok"}
    assert result.widget is not None


def test_division_standings_evolution_requires_division_id():
    from pytest import raises

    with raises(ValueError):
        chart_registry.build(ChartRequest(chart_type="division.standings.evolution", data={}))
