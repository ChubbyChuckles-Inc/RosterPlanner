import pytest

from gui.design.component_maturity import (
    ComponentMaturity,
    register_component_maturity,
    get_component_maturity,
    list_component_maturity,
    clear_component_maturity,
    summarize_maturity,
)


def setup_function(_):  # runs before each test
    clear_component_maturity()


def test_register_and_get():
    entry = ComponentMaturity(
        component_id="roster-table",
        status="alpha",
        description="Initial roster table implementation",
        risks="Performance on large datasets",
        since_version="0.1.0",
    )
    register_component_maturity(entry)
    fetched = get_component_maturity("roster-table")
    assert fetched == entry
    assert fetched.badge_label() == "ALPHA"


def test_duplicate_id_rejected():
    entry = ComponentMaturity("comp", "beta", "Test")
    register_component_maturity(entry)
    with pytest.raises(ValueError):
        register_component_maturity(entry)


def test_invalid_status_rejected():
    bad = ComponentMaturity("comp2", "experimental", "Bad status")
    with pytest.raises(ValueError):
        register_component_maturity(bad)


def test_list_and_summary():
    register_component_maturity(ComponentMaturity("a", "alpha", "A"))
    register_component_maturity(ComponentMaturity("b", "beta", "B"))
    register_component_maturity(ComponentMaturity("c", "stable", "C"))
    all_entries = list_component_maturity()
    assert len(all_entries) == 3
    summary = summarize_maturity()
    assert summary["alpha"] == 1
    assert summary["beta"] == 1
    assert summary["stable"] == 1
