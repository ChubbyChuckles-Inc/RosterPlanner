import pytest

from gui.ingestion.rule_schema import (
    RuleSet,
    TableRule,
    ListRule,
    FieldMapping,
    RuleError,
    TransformSpec,
)


def test_ruleset_round_trip_table():
    payload = {
        "version": 1,
        "resources": {
            "ranking_table": {
                "kind": "table",
                "selector": "table.ranking",
                "columns": ["team", "points", "diff"],
            }
        },
    }
    rs = RuleSet.from_mapping(payload)
    assert rs.version == 1
    assert rs.resource_kind("ranking_table") == "table"
    back = rs.to_mapping()
    assert back["resources"]["ranking_table"]["columns"] == ["team", "points", "diff"]


def test_ruleset_list_rule_and_field_mapping_variants():
    payload = {
        "resources": {
            "team_roster": {
                "kind": "list",
                "selector": "div.roster",
                "item_selector": "div.player",
                "fields": {
                    "name": ".name",
                    "live_pz": {"selector": ".lpz"},
                },
            }
        }
    }
    rs = RuleSet.from_mapping(payload)
    assert rs.resource_kind("team_roster") == "list"
    lst = rs.ensure_resource("team_roster")
    assert isinstance(lst, ListRule)
    assert set(lst.fields.keys()) == {"name", "live_pz"}


def test_field_mapping_with_transforms_round_trip():
    payload = {
        "version": 1,
        "resources": {
            "team_roster": {
                "kind": "list",
                "selector": "div.roster",
                "item_selector": "div.player",
                "fields": {
                    "name": {"selector": ".name", "transforms": ["trim", "collapse_ws"]},
                    "points": {
                        "selector": ".pts",
                        "transforms": ["trim", {"kind": "to_number"}],
                    },
                    "date_joined": {
                        "selector": ".joined",
                        "transforms": [{"kind": "parse_date", "formats": ["%d.%m.%Y", "%Y-%m-%d"]}],
                    },
                },
            }
        },
    }
    rs = RuleSet.from_mapping(payload)
    fm = rs.ensure_resource("team_roster").fields["points"]  # type: ignore[attr-defined]
    assert len(fm.transforms) == 2
    back = rs.to_mapping()
    # Simple transforms serialized as strings
    tlist = back["resources"]["team_roster"]["fields"]["name"]["transforms"]
    assert tlist == ["trim", "collapse_ws"]
    # parse_date retains structure
    dspec = back["resources"]["team_roster"]["fields"]["date_joined"]["transforms"][0]
    assert dspec["kind"] == "parse_date" and len(dspec["formats"]) == 2


def test_expression_transform_requires_flag():
    payload = {
        "resources": {
            "team_roster": {
                "kind": "list",
                "selector": "div.roster",
                "item_selector": "div.player",
                "fields": {
                    "norm": {
                        "selector": ".val",
                        "transforms": [{"kind": "expr", "code": "value.replace(',', '.')"}],
                    }
                },
            }
        }
    }
    with pytest.raises(RuleError):
        RuleSet.from_mapping(payload)
    # Enable expressions
    payload["allow_expressions"] = True
    rs = RuleSet.from_mapping(payload)
    back = rs.to_mapping()
    assert back["allow_expressions"] is True
    expr_spec = back["resources"]["team_roster"]["fields"]["norm"]["transforms"][0]
    assert expr_spec["kind"] == "expr" and "code" in expr_spec


@pytest.mark.parametrize(
    "transform, msg",
    [
        ("", "empty"),
        ("unknown_kind", "Unsupported"),
        ({"kind": "parse_date", "formats": []}, "parse_date"),
        ({"kind": "expr", "code": "value"}, "disabled"),  # expr without flag
    ],
)
def test_invalid_transforms(transform, msg):
    payload = {
        "resources": {
            "x": {
                "kind": "list",
                "selector": "div.r",
                "item_selector": "div.i",
                "fields": {"f": {"selector": ".f", "transforms": [transform]}},
            }
        }
    }
    with pytest.raises(RuleError) as e:
        RuleSet.from_mapping(payload)
    assert msg.lower() in str(e.value).lower()


@pytest.mark.parametrize(
    "bad_payload, expected",
    [
        ({"resources": {"x": {"kind": "table", "selector": "", "columns": ["a"]}}}, "selector"),
        ({"resources": {"x": {"kind": "table", "selector": "t", "columns": []}}}, "columns"),
        (
            {
                "resources": {
                    "x": {"kind": "list", "selector": "s", "item_selector": "", "fields": {}}
                }
            },
            "item_selector",
        ),
        ({"resources": {"x": {"kind": "unknown"}}}, "unsupported"),
    ],
)
def test_ruleset_validation_errors(bad_payload, expected):
    with pytest.raises(RuleError) as e:
        RuleSet.from_mapping(bad_payload)
    assert expected in str(e.value)
