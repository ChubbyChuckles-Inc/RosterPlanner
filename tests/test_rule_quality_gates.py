from gui.ingestion.rule_schema import RuleSet
from gui.ingestion.rule_quality_gates import evaluate_quality_gates


def _ruleset():
    payload = {
        "version": 1,
        "resources": {
            "ranking": {"kind": "table", "selector": "table.r", "columns": ["team", "pts"]},
            "players": {
                "kind": "list",
                "selector": "ul.p",
                "item_selector": "li",
                "fields": {"name": {"selector": "span.n"}, "rank": {"selector": "span.rank"}},
            },
        },
    }
    return RuleSet.from_mapping(payload)


def test_quality_gates_basic():
    rs = _ruleset()
    html_by_file = {
        "f": """
        <html><body>
        <table class='r'><tr><th>Team</th><th>Pts</th></tr>
        <tr><td>A</td><td>5</td></tr>
        <tr><td>B</td><td>7</td></tr>
        </table>
        <ul class='p'>
            <li><span class='n'>Alice</span><span class='rank'>1</span></li>
            <li><span class='n'>Bob</span></li>
        </ul>
        </body></html>
        """,
    }
    gates = {"players.name": 1.0, "players.rank": 0.75, "ranking.pts": 1.0}
    report = evaluate_quality_gates(rs, html_by_file, gates)
    mapping = {f"{r.resource}.{r.field}": r for r in report.results}
    assert mapping["players.name"].passed is True
    # players.rank has ratio 0.5 (1/2) < 0.75 threshold
    assert mapping["players.rank"].passed is False
    # ranking table has 2 rows with all pts populated (1.0)
    assert mapping["ranking.pts"].passed is True
    assert report.failed_count == 1
    assert report.passed is False
