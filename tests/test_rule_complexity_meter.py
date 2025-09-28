import pytest

from gui.ingestion.rule_complexity_meter import (
    RuleComplexityError,
    compute_rule_complexity,
)


def test_complexity_low_grade_for_simple_table():
    payload = {
        "resources": {
            "ranking": {
                "kind": "table",
                "selector": "table",
                "columns": ["team", "points", "diff"],
            }
        }
    }
    report = compute_rule_complexity(payload)
    assert report.grade == "Low"
    assert report.badge == "low"
    assert report.max_score <= 6
    assert report.field_count == 3
    assert report.to_mapping()["details"][0]["selector_depth"] == 1


def test_complexity_high_grade_for_nested_selectors_and_transforms():
    payload = {
        "allow_expressions": True,
        "transform_macros": {
            "HeavyCleanup": [
                "trim",
                {"kind": "collapse_ws"},
                {"kind": "expr", "code": "value.strip()"},
            ]
        },
        "resources": {
            "base": {
                "kind": "list",
                "selector": "div.root > section.area .container",
                "item_selector": "div.card.player",
                "fields": {
                    "name": {"selector": "span.name", "transforms": ["trim"]},
                },
            },
            "child": {
                "kind": "list",
                "extends": "base",
                "fields": {
                    "score": {
                        "selector": "div.stats ul li span.value",
                        "macros": ["HeavyCleanup"],
                        "transforms": [
                            {"kind": "parse_date", "formats": ["%d.%m.%Y"]},
                            "collapse_ws",
                            {"kind": "expr", "code": "value"},
                        ],
                    }
                },
            },
        },
    }
    report = compute_rule_complexity(payload)
    assert report.grade == "High"
    assert report.badge == "high"
    assert report.max_score > 12
    assert report.field_count >= 2
    tooltip = report.guidance
    assert "Complex" in tooltip or "Complex".lower() in tooltip.lower()


def test_complexity_invalid_payload_raises():
    with pytest.raises(RuleComplexityError):
        compute_rule_complexity("not valid json")
