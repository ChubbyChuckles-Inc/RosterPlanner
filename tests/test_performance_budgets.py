from gui.design import (
    list_performance_budgets,
    get_performance_budget,
    enforce_budget,
    PerformanceBudget,
)


def test_registry_contains_expected_components():
    names = [b.name for b in list_performance_budgets()]
    for expected in [
        "NavigationTree",
        "DetailView-Team",
        "StatsPanel",
        "PlannerScenarioEditor",
        "ChartCanvas",
    ]:
        assert expected in names


def test_budget_fields_and_order():
    budgets = list_performance_budgets()
    # Sorted order by name
    assert [b.name for b in budgets] == sorted(b.name for b in budgets)
    for b in budgets:
        assert isinstance(b, PerformanceBudget)
        assert b.render_ms > 0
        assert b.update_ms > 0
        assert b.frame_ms > 0
        assert b.frame_ms < 16.7  # 60 FPS budget safety


def test_get_budget_lookup():
    b = get_performance_budget("NavigationTree")
    assert b.name == "NavigationTree"


def test_enforce_budget_passes_when_within_limits():
    sample = {
        "NavigationTree": {"render_ms": 20.0, "update_ms": 5.5, "frame_ms": 1.0},
        "ChartCanvas": {"render_ms": 30.0, "update_ms": 10.0, "frame_ms": 3.0},
    }
    violations = enforce_budget(sample)
    assert violations == []


def test_enforce_budget_flags_violations():
    sample = {
        "NavigationTree": {"render_ms": 40.0, "update_ms": 5.5, "frame_ms": 1.0},  # render over
        "UnknownWidget": {"render_ms": 1.0, "update_ms": 1.0, "frame_ms": 1.0},
        "ChartCanvas": {"render_ms": 30.0, "update_ms": 20.0},  # missing frame_ms & update over
    }
    violations = enforce_budget(sample)
    assert any("over-budget" in v for v in violations)
    assert any("unknown-component" in v for v in violations)
    assert any("missing-metric" in v for v in violations)
