from gui.ingestion.rule_schema import RuleSet
from gui.ingestion.rule_adapter import adapt_ruleset_over_files

def _ruleset():
    return RuleSet.from_mapping({
        "version": 1,
        "resources": {
            "players": {
                "kind": "list",
                "selector": "ul.p",
                "item_selector": "li",
                "fields": {"name": {"selector": "span.n"}, "rank": {"selector": "span.r"}},
            },
            "ranking": {"kind": "table", "selector": "table.r", "columns": ["team", "pts"]},
        },
    })

HTML_A = """
<html><body>
<table class='r'><tr><th>Team</th><th>Pts</th></tr>
<tr><td>A</td><td>5</td></tr>
<tr><td>B</td><td>7</td></tr>
</table>
<ul class='p'>
  <li><span class='n'>Alice</span><span class='r'>1</span></li>
  <li><span class='n'>Bob</span><span class='r'>2</span></li>
</ul>
</body></html>
"""

HTML_B = """
<html><body>
<table class='r'><tr><th>Team</th><th>Pts</th></tr>
<tr><td>A</td><td>5</td></tr>
<tr><td>C</td><td>9</td></tr>
</table>
<ul class='p'>
  <li><span class='n'>Cara</span><span class='r'>3</span></li>
</ul>
</body></html>
"""

def test_adapter_basic_dedup():
    rs = _ruleset()
    bundle = adapt_ruleset_over_files(rs, {"f1": HTML_A, "f2": HTML_B})
    players = bundle.resources["players"]
    ranking = bundle.resources["ranking"]
    # Ranking rows: 3 unique (A,5) appears in both but deduped once, plus B and C
    assert len(ranking.rows) == 3
    # Players rows: 3 unique players
    assert len(players.rows) == 3
    assert set(players.source_files) == {"f1", "f2"}
