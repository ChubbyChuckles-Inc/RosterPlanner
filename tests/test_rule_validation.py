import pytest

from gui.ingestion.rule_schema import RuleSet, RuleError
from gui.ingestion.rule_validation import validate_rules

SIMPLE_HTML = {
    "team": """
    <html><body>
      <div class='roster'>
        <div class='player'><span class='name'>Alice</span><span class='val'>10</span></div>
        <div class='player'><span class='name'>Bob</span><span class='val'>12</span></div>
      </div>
      <table class='ranking'>
        <tr><th>Team</th><th>Points</th></tr>
        <tr><td>X</td><td>5</td></tr>
      </table>
    </body></html>
    """,
}


def build_rules():
    return RuleSet.from_mapping(
        {
            "resources": {
                "team_roster": {
                    "kind": "list",
                    "selector": "div.roster",
                    "item_selector": "div.player",
                    "fields": {"name": {"selector": ".name"}, "value": {"selector": ".val"}},
                },
                "ranking_table": {
                    "kind": "table",
                    "selector": "table.ranking",
                    "columns": ["team", "points"],
                },
            }
        }
    )


def test_validation_basic_counts():
    rs = build_rules()
    rep = validate_rules(rs, SIMPLE_HTML)
    roster = rep.resources["team_roster"]
    assert roster.selector_count == 1
    assert roster.item_count == 2
    assert roster.fields["name"].matched_items == 2
    assert roster.fields["value"].matched_items == 2
    table = rep.resources["ranking_table"]
    assert table.selector_count == 1
    assert not rep.warnings


def test_validation_field_missing():
    rs = RuleSet.from_mapping(
        {
            "resources": {
                "team_roster": {
                    "kind": "list",
                    "selector": "div.roster",
                    "item_selector": "div.player",
                    "fields": {"name": {"selector": ".name"}, "missing": {"selector": ".zzz"}},
                }
            }
        }
    )
    rep = validate_rules(rs, SIMPLE_HTML)
    assert any("missing" in w for w in rep.warnings)


def test_validation_zero_root():
    rs = RuleSet.from_mapping(
        {
            "resources": {
                "bad": {"kind": "list", "selector": "div.none", "item_selector": "div.player", "fields": {"x": ".name"}}
            }
        }
    )
    rep = validate_rules(rs, SIMPLE_HTML)
    assert any("matched 0 nodes" in w for w in rep.warnings)


def test_requires_html_document():
    rs = build_rules()
    with pytest.raises(RuleError):
        validate_rules(rs, {})
