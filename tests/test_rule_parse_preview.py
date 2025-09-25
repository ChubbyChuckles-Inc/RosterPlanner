from gui.ingestion.rule_schema import RuleSet
from gui.ingestion.rule_parse_preview import generate_parse_preview

HTML_DOC = """
<html>
  <body>
    <table class='ranking'>
      <tr><th>Team</th><th>Points</th></tr>
      <tr><td>A</td><td>10</td></tr>
      <tr><td>B</td><td>12</td></tr>
    </table>
    <div class='roster'>
      <div class='player'><span class='name'> Alice </span><span class='pts'>11</span></div>
      <div class='player'><span class='name'>Bob</span><span class='pts'>  9 </span></div>
    </div>
  </body>
</html>
"""

RULES = RuleSet.from_mapping(
    {
        "allow_expressions": False,
        "resources": {
            "ranking_table": {
                "kind": "table",
                "selector": "table.ranking",
                "columns": ["team", "points"],
            },
            "team_roster": {
                "kind": "list",
                "selector": "div.roster",
                "item_selector": "div.player",
                "fields": {
                    "name": {"selector": ".name", "transforms": ["trim"]},
                    "points": {
                        "selector": ".pts",
                        "transforms": ["trim", {"kind": "to_number"}],
                    },
                },
            },
        },
    }
)


def test_parse_preview_without_transforms():
    preview = generate_parse_preview(RULES, HTML_DOC, apply_transforms=False)
    # Table rows
    assert len(preview.extracted_records["ranking_table"]) == 2
    # List records raw (not coerced): whitespace preserved for first name, numeric still string
    roster = preview.extracted_records["team_roster"]
    assert roster[0]["name"].startswith("Alice")  # leading space trimmed? not yet because trim transform skipped
    # because apply_transforms=False, numeric not coerced
    assert isinstance(roster[0]["points"], str)


def test_parse_preview_with_transforms():
    preview = generate_parse_preview(RULES, HTML_DOC, apply_transforms=True)
    roster = preview.extracted_records["team_roster"]
    # Trim applied
    assert roster[0]["name"] == "Alice"
    # to_number applied
    assert roster[0]["points"] == 11 and isinstance(roster[0]["points"], int)
    # match spans contain selectors
    assert any(m["selector"].startswith("div.roster") for m in preview.match_spans["team_roster"])