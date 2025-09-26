import pytest

from gui.ingestion.rule_schema import RuleSet, RuleError


def test_ruleset_valid_table_and_list():
    payload = {
        "version": 1,
        "resources": {
            "ranking_table": {"kind": "table", "selector": "table.ranking", "columns": ["team", "points"]},
            "team_roster": {
                "kind": "list",
                "selector": "div.roster",
                "item_selector": "div.player",
                "fields": {"name": ".name", "rating": {"selector": ".lpz", "transforms": ["trim", "to_number"]}},
            },
        },
    }
    rs = RuleSet.from_mapping(payload)
    assert sorted(rs.list_resources()) == ["ranking_table", "team_roster"]
    assert rs.resource_kind("ranking_table") == "table"
    assert rs.resource_kind("team_roster") == "list"


@pytest.mark.parametrize(
    "bad_payload, expected_sub",
    [
        ({"resources": {"t": {"kind": "table", "selector": "", "columns": ["a"]}}}, "selector"),
        ({"resources": {"t": {"kind": "table", "selector": "x", "columns": []}}}, "columns"),
        ({"resources": {"l": {"kind": "list", "selector": "div", "item_selector": "", "fields": {}}}}, "item_selector"),
        ({"resources": {"l": {"kind": "list", "selector": "div", "item_selector": "i", "fields": {}}}}, "fields"),
        ({"resources": {"t": {"kind": "table", "selector": "x", "columns": ["a", "a"]}}}, "Duplicate"),
    ],
)
def test_ruleset_invalid_cases(bad_payload, expected_sub):
    with pytest.raises(RuleError) as ei:
        RuleSet.from_mapping(bad_payload)
    assert expected_sub.lower() in str(ei.value).lower()


def test_transform_expression_disabled():
    payload = {
        "resources": {
            "l": {
                "kind": "list",
                "selector": "div",
                "item_selector": "li",
                "fields": {"name": {"selector": ".n", "transforms": [{"kind": "expr", "code": "value"}]}},
            }
        }
    }
    with pytest.raises(RuleError):
        RuleSet.from_mapping(payload)


def test_transform_expression_enabled():
    payload = {
        "allow_expressions": True,
        "resources": {
            "l": {
                "kind": "list",
                "selector": "div",
                "item_selector": "li",
                "fields": {"name": {"selector": ".n", "transforms": [{"kind": "expr", "code": "value.strip()"}]}},
            }
        },
    }
    rs = RuleSet.from_mapping(payload)
    assert rs.allow_expressions is True


def compute_mapping_diff(old: dict, new: dict):  # minimalist helper for test demonstration
    removed = sorted(set(old) - set(new))
    added = sorted(set(new) - set(old))
    changed = []
    for k in set(old).intersection(new):
        if old[k] != new[k]:
            changed.append(k)
    return {"added": sorted(added), "removed": sorted(removed), "changed": sorted(changed)}


def test_mapping_diff_helper():
    old = {"a": 1, "b": 2, "c": 3}
    new = {"b": 2, "c": 4, "d": 9}
    diff = compute_mapping_diff(old, new)
    assert diff == {"added": ["d"], "removed": ["a"], "changed": ["c"]}
