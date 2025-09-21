"""Tests for adaptive reflow rules (Milestone 0.21.1)."""

import pytest
from gui.design.reflow import list_reflow_rules, get_reflow_actions, ReflowRule


def test_rules_registered_order():
    rules = list_reflow_rules()
    names = [r.name for r in rules]
    assert names == [
        "xs-collapse",
        "sm-narrow",
        "md-standard",
        "lg-aux",
        "xl-wide",
    ]


@pytest.mark.parametrize(
    "width,expected_contains,not_contains",
    [
        (320, ["collapse_nav_to_icons", "stack_side_panels"], ["enable_aux_panel"]),
        (700, ["collapse_nav_to_icons"], ["stack_side_panels"]),  # sm: no stack_side_panels
        (899, ["collapse_nav_to_icons", "show_compact_toolbar"], ["enable_aux_panel"]),
        (900, ["standard_layout"], ["collapse_nav_to_icons"]),
        (1280, ["enable_aux_panel", "standard_layout"], ["enable_extra_summary_panel"]),
        (1700, ["enable_extra_summary_panel"], []),
    ],
)
def test_action_sets(width, expected_contains, not_contains):
    actions = get_reflow_actions(width)
    for a in expected_contains:
        assert a in actions, f"Expected action {a} for width {width}"
    for a in not_contains:
        assert a not in actions, f"Unexpected action {a} for width {width}"


def test_action_order_is_first_occurrence():
    # width beyond 1600 includes actions from xl-wide rule only (plus layered earlier rule logic not matching)
    actions = get_reflow_actions(2000)
    # Order should reflect rule action sequence
    assert actions[0] == "enable_aux_panel"
    assert actions[1] == "enable_extra_summary_panel"
    assert actions[-1] == "standard_layout"


def test_negative_width_rejected():
    with pytest.raises(ValueError):
        get_reflow_actions(-5)
