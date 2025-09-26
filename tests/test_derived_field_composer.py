import json
from gui.ingestion.derived_field_composer import (
    gather_available_fields,
    validate_expression,
    update_ruleset_with_derived,
)


def sample_rules():
    return {
        "version": 1,
        "resources": {
            "ranking_table": {
                "kind": "table",
                "selector": "table.ranking",
                "columns": ["team", "points", "diff"],
            },
            "team_roster": {
                "kind": "list",
                "selector": "div.roster",
                "item_selector": "div.player",
                "fields": {
                    "name": {"selector": ".name"},
                    "live_pz": {"selector": ".lpz"},
                },
            },
        },
    }


def test_gather_available_fields():
    fields = gather_available_fields(sample_rules())
    assert {"team", "points", "diff", "name", "live_pz"}.issubset(fields)


def test_validate_expression_allows_basic_arithmetic():
    fields = gather_available_fields(sample_rules())
    refs = validate_expression("points - diff", fields)
    assert refs == {"points", "diff"}


def test_validate_expression_rejects_unknown():
    fields = gather_available_fields(sample_rules())
    try:
        validate_expression("points + missing", fields)
    except ValueError as e:
        assert "Unknown field" in str(e)
    else:
        assert False, "Expected ValueError"


def test_validate_expression_requires_reference():
    fields = gather_available_fields(sample_rules())
    try:
        validate_expression("1 + 2", fields)
    except ValueError as e:
        assert "must reference" in str(e)
    else:
        assert False, "Expected ValueError"


def test_update_ruleset_with_derived_merges():
    raw = json.dumps(sample_rules())
    updated = update_ruleset_with_derived(raw, {"ratio": "points / diff"})
    data = json.loads(updated)
    assert data["derived"]["ratio"] == "points / diff"
    # second merge
    updated2 = update_ruleset_with_derived(updated, {"p2": "points"})
    data2 = json.loads(updated2)
    assert set(data2["derived"].keys()) == {"ratio", "p2"}


def test_validate_expression_disallows_call():
    fields = gather_available_fields(sample_rules())
    try:
        validate_expression("len(points)", fields)
    except ValueError as e:
        # Should flag Call (not in allowed nodes)
        assert "Disallowed syntax" in str(e)
    else:
        assert False, "Expected ValueError for call"
