"""Tests for Field Coverage Radar categorization logic (Milestone 7.10.A5).

Focus exclusively on the pure logic function ``categorize_coverage`` to avoid
GUI dependencies (painting / QWidgets) in CI. The widget itself is lightweight
and exercised manually.
"""

from gui.ingestion.field_coverage_radar import categorize_coverage
from gui.ingestion.rule_field_coverage import (
    FieldCoverageReport,
    FieldCoverageResource,
    FieldCoverageField,
)


def _make_report(fields):
    # fields: list of tuples (name, non_empty, total)
    res = FieldCoverageResource(
        resource="sample",
        kind="list",
        fields=[
            FieldCoverageField(
                field=name,
                target_column=name,
                non_empty=non_empty,
                total_rows=total,
                distinct=non_empty,
            )
            for name, non_empty, total in fields
        ],
    )
    return FieldCoverageReport(
        resources=[res],
        total_target_columns=len(res.fields),
        total_non_empty_cells=sum(f.non_empty for f in res.fields),
        total_possible_cells=sum(f.total_rows for f in res.fields),
    )


def test_categorize_basic_groups():
    report = _make_report(
        [
            ("player_name", 10, 10),  # identity 100%
            ("live_rating", 5, 10),  # performance 50%
            ("match_count", 8, 10),  # performance 80%
            ("fixture_date", 0, 10),  # schedule 0%
            ("notes", 2, 10),  # meta 20%
        ]
    )
    cats = categorize_coverage(report)
    names = [c.category for c in cats]
    assert names == ["identity", "performance", "schedule", "meta"]
    # identity average ratio
    ident = next(c for c in cats if c.category == "identity")
    assert round(ident.average_ratio, 2) == 1.0
    perf = next(c for c in cats if c.category == "performance")
    # (0.5 + 0.8)/2 = 0.65
    assert abs(perf.average_ratio - 0.65) < 1e-6
    schedule = next(c for c in cats if c.category == "schedule")
    assert schedule.average_ratio == 0.0
    meta = next(c for c in cats if c.category == "meta")
    assert round(meta.average_ratio, 2) == 0.20


def test_categorize_handles_no_fields():
    # Empty report -> categories still present with zero ratios
    empty_report = _make_report([])
    cats = categorize_coverage(empty_report)
    for c in cats:
        assert c.average_ratio == 0.0
