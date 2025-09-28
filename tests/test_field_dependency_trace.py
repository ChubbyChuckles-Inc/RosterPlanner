from gui.ingestion.field_dependency_trace import (
    TraceBuildError,
    build_field_trace,
    list_derived_fields,
)


def make_sample_mapping():
    return {
        "allow_expressions": True,
        "transform_macros": {
            "CleanNumber": ["trim", {"kind": "to_number"}],
        },
        "resources": {
            "team_roster": {
                "kind": "list",
                "selector": "div.roster",
                "item_selector": "div.player",
                "fields": {
                    "points": {"selector": ".pts", "macros": ["CleanNumber"]},
                    "games": {"selector": ".games", "macros": ["CleanNumber"]},
                    "ratio": {
                        "selector": ".ratio",
                        "transforms": [
                            "trim",
                            {"kind": "expr", "code": "points / games"},
                        ],
                    },
                },
            }
        },
        "derived": {
            "ratio_bonus": "ratio * 1.1",
            "points_diff": "points - games",
        },
    }


def test_list_derived_fields_sorted_unique():
    mapping = make_sample_mapping()
    names = list_derived_fields(mapping)
    assert names == ["points_diff", "ratio_bonus"]


def test_build_field_trace_with_macros_and_nested_refs():
    mapping = make_sample_mapping()
    steps = build_field_trace(mapping, "ratio_bonus")
    # Derived field first
    assert steps[0].name == "ratio_bonus"
    assert steps[0].type == "derived"
    assert steps[0].depth == 0
    assert steps[0].expression == "ratio * 1.1"
    # Ratio field
    ratio_step = next(step for step in steps if step.name == "ratio" and step.type == "list_field")
    assert ratio_step.depth == 1
    assert ratio_step.resource == "team_roster"
    kinds = [t.kind for t in ratio_step.transforms]
    assert kinds == ["trim", "expr"]
    expr_transform = ratio_step.transforms[-1]
    assert expr_transform.code == "points / games"
    # Points field sourced from macro
    points_step = next(
        step for step in steps if step.name == "points" and step.type == "list_field"
    )
    assert points_step.depth == 2
    assert points_step.resource == "team_roster"
    assert [t.kind for t in points_step.transforms] == ["trim", "to_number"]
    assert all(t.macro == "CleanNumber" for t in points_step.transforms)
    # Games field similar to points
    games_step = next(step for step in steps if step.name == "games" and step.type == "list_field")
    assert [t.kind for t in games_step.transforms] == ["trim", "to_number"]


def test_build_field_trace_missing_field_raises():
    mapping = make_sample_mapping()
    try:
        build_field_trace(mapping, "missing")
    except TraceBuildError as exc:
        assert "missing" in str(exc)
    else:  # pragma: no cover - ensure failure if exception not raised
        raise AssertionError("TraceBuildError expected")
