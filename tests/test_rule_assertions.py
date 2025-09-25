from gui.ingestion.rule_schema import RuleSet
from gui.ingestion.rule_parse_preview import generate_parse_preview
from gui.ingestion.rule_assertions import (
    AssertionSpec,
    evaluate_assertions,
)


def _ruleset():
    payload = {
        "version": 1,
        "resources": {
            "ranking": {
                "kind": "table",
                "selector": "table.ranking",
                "columns": ["team", "points"],
            },
            "players": {
                "kind": "list",
                "selector": "ul.players",
                "item_selector": "li",
                "fields": {"name": {"selector": "span.name"}},
            },
        },
    }
    return RuleSet.from_mapping(payload)


def test_assertions_basic_pass_and_fail():
    rs = _ruleset()
    html = """
    <html><body>
    <table class='ranking'>
      <tr><th>Team</th><th>Pts</th></tr>
      <tr><td>Alpha</td><td>10</td></tr>
      <tr><td>Beta</td><td>8</td></tr>
    </table>
    <ul class='players'>
      <li><span class='name'>Alice</span></li>
      <li><span class='name'>Bob</span></li>
    </ul>
    </body></html>
    """
    preview = generate_parse_preview(rs, html, apply_transforms=False, capture_performance=False)
    specs = [
        AssertionSpec(resource="ranking", field="team", expect="Alpha", index=0),  # pass
        AssertionSpec(resource="ranking", field="team", expect="Gamma", index=1),  # fail
        AssertionSpec(resource="players", field="name", expect="Ali", index=0, op="contains"),  # pass contains
        AssertionSpec(resource="players", field="name", expect="Carl", index=2),  # index oob
        AssertionSpec(resource="missing", field="x", expect="y"),  # missing resource
    ]
    results = evaluate_assertions(rs, preview, specs)
    assert len(results) == 5
    statuses = [r.passed for r in results]
    assert statuses == [True, False, True, False, False]
    # Ensure messages populated
    assert any("expected" in r.message for r in results if not r.passed)


def test_assertions_field_missing():
    rs = _ruleset()
    html = "<html><body><table class='ranking'><tr><th>Team</th><th>Pts</th></tr><tr><td>Alpha</td><td>10</td></tr></table></body></html>"
    preview = generate_parse_preview(rs, html, apply_transforms=False, capture_performance=False)
    spec = AssertionSpec(resource="ranking", field="not_a_col", expect="", index=0)
    res = evaluate_assertions(rs, preview, [spec])[0]
    assert not res.passed and "field" in res.message.lower()
