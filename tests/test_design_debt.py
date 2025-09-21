from gui.design.design_debt import (
    DesignDebtItem,
    register_design_debt,
    get_design_debt,
    list_design_debt,
    filter_design_debt,
    close_design_debt,
    summarize_design_debt,
    clear_design_debt,
)
import pytest


def setup_function(_):
    clear_design_debt()


def test_register_and_get():
    item = DesignDebtItem(
        debt_id="color_tokens_inconsistent",
        title="Color token mismatch",
        severity="medium",
        description="Some components use hardcoded hex values instead of tokens.",
        introduced_in="0.49",
        tags=("theming",),
    )
    register_design_debt(item)
    fetched = get_design_debt("color_tokens_inconsistent")
    assert fetched == item


def test_duplicate_prevention():
    item = DesignDebtItem(
        debt_id="dup",
        title="Dup",
        severity="low",
        description="a",
        introduced_in="0.49",
    )
    register_design_debt(item)
    with pytest.raises(ValueError):
        register_design_debt(item)


def test_invalid_severity():
    bad = DesignDebtItem(
        debt_id="bad",
        title="Bad",
        severity="severe",  # invalid
        description="invalid severity",
        introduced_in="0.49",
    )
    with pytest.raises(ValueError):
        register_design_debt(bad)


def test_filter_by_severity_and_tags():
    register_design_debt(
        DesignDebtItem(
            debt_id="a",
            title="A",
            severity="low",
            description="",
            introduced_in="0.49",
            tags=("a11y",),
        )
    )
    register_design_debt(
        DesignDebtItem(
            debt_id="b",
            title="B",
            severity="high",
            description="",
            introduced_in="0.49",
            tags=("theming",),
        )
    )
    register_design_debt(
        DesignDebtItem(
            debt_id="c",
            title="C",
            severity="critical",
            description="",
            introduced_in="0.49",
            tags=("a11y", "performance"),
        )
    )

    # Filter by severity
    highs = filter_design_debt(severities=["high", "critical"])
    assert {i.debt_id for i in highs} == {"b", "c"}

    # Filter by tag intersection
    a11y = filter_design_debt(tags=["a11y"])
    assert {i.debt_id for i in a11y} == {"a", "c"}

    # Combined filter
    combo = filter_design_debt(severities=["critical"], tags=["performance"])  # c qualifies
    assert [i.debt_id for i in combo] == ["c"]


def test_close_and_list_open_only():
    register_design_debt(
        DesignDebtItem(
            debt_id="x",
            title="X",
            severity="low",
            description="",
            introduced_in="0.49",
        )
    )
    register_design_debt(
        DesignDebtItem(
            debt_id="y",
            title="Y",
            severity="high",
            description="",
            introduced_in="0.49",
        )
    )
    close_design_debt("x")
    open_only = list_design_debt(include_closed=False)
    assert {i.debt_id for i in open_only} == {"y"}


def test_summary_counts():
    register_design_debt(
        DesignDebtItem(
            debt_id="a",
            title="A",
            severity="low",
            description="",
            introduced_in="0.49",
        )
    )
    register_design_debt(
        DesignDebtItem(
            debt_id="b",
            title="B",
            severity="low",
            description="",
            introduced_in="0.49",
        )
    )
    register_design_debt(
        DesignDebtItem(
            debt_id="c",
            title="C",
            severity="critical",
            description="",
            introduced_in="0.49",
        )
    )
    close_design_debt("b")
    summary = summarize_design_debt()
    assert summary["severity_low"] == 2
    assert summary["severity_critical"] == 1
    assert summary["open"] == 2  # a + c
    assert summary["closed"] == 1  # b
