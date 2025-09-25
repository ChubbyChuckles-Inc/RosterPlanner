from gui.ingestion.rule_schema import RuleSet
from gui.ingestion.rule_field_coverage import compute_field_coverage


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


def test_field_coverage_basic():
    rs = _ruleset()
    html_by_file = {
        "f1": """
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
        "f2": """
        <html><body>
        <table class='r'><tr><th>Team</th><th>Pts</th></tr>
        <tr><td>C</td><td>9</td></tr>
        </table>
        <ul class='p'>
            <li><span class='n'>Cara</span><span class='rank'>2</span></li>
        </ul>
        </body></html>
        """,
    }
    report = compute_field_coverage(rs, html_by_file)
    ranking = next(r for r in report.resources if r.resource == "ranking")
    players = next(r for r in report.resources if r.resource == "players")
    # Ranking table: 3 data rows, both columns populated fully => coverage 1.0
    for fc in ranking.fields:
        assert fc.coverage_ratio == 1.0
        assert fc.non_empty == 3
        assert fc.total_rows == 3
    # Players list: total rows 3 (2 + 1); name filled in all 3, rank only 2 => ratios 1.0, 2/3
    name_field = next(f for f in players.fields if f.field == "name")
    rank_field = next(f for f in players.fields if f.field == "rank")
    assert name_field.non_empty == 3 and name_field.total_rows == 3
    assert rank_field.non_empty == 2 and rank_field.total_rows == 3
    # Overall ratio should reflect aggregate cells: ranking(2 cols *3 rows=6 non-empty) + players( name 3 + rank 2 =5 ) =11 / total possible ( (2*3)+(2*3)=12 ) => 11/12
    assert abs(report.overall_ratio - (11 / 12)) < 1e-9
