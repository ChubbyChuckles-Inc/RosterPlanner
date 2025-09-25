from gui.ingestion.rule_schema import RuleSet
from gui.ingestion.rule_diff import diff_rule_sets


def _ruleset_a():
    payload = {
        "version": 1,
        "resources": {
            "ranking": {"kind": "table", "selector": "table.r", "columns": ["team", "pts"]},
            "players": {
                "kind": "list",
                "selector": "ul.p",
                "item_selector": "li",
                "fields": {"name": {"selector": "span.n"}},
            },
        },
    }
    return RuleSet.from_mapping(payload)


def _ruleset_b_modified():
    payload = {
        "version": 1,
        "resources": {
            "ranking": {"kind": "table", "selector": "table.r", "columns": ["team", "pts"]},
            # players list renamed field or additional row will produce diff
            "players": {
                "kind": "list",
                "selector": "ul.p",
                "item_selector": "li",
                "fields": {"name": {"selector": "span.n"}},
            },
            "new_resource": {
                "kind": "list",
                "selector": "div.extra",
                "item_selector": "span",
                "fields": {"val": {"selector": "span"}},
            },
        },
    }
    return RuleSet.from_mapping(payload)


def test_diff_rule_sets_basic():
    rs_a = _ruleset_a()
    rs_b = _ruleset_b_modified()
    html_by_file = {
        "file1": """
        <html><body>
        <table class='r'><tr><th>Team</th><th>Pts</th></tr><tr><td>A</td><td>5</td></tr></table>
        <ul class='p'><li><span class='n'>Alice</span></li></ul>
        <div class='extra'><span>ignored</span></div>
        </body></html>
        """,
        "file2": """
        <html><body>
        <table class='r'><tr><th>Team</th><th>Pts</th></tr><tr><td>B</td><td>7</td></tr></table>
        <ul class='p'><li><span class='n'>Bob</span></li></ul>
        <div class='extra'><span>X</span></div>
        </body></html>
        """,
    }
    res = diff_rule_sets(rs_a, rs_b, html_by_file)
    # Ensure we have entries for union of resources
    names = {r.name for r in res.resources}
    assert {"ranking", "players", "new_resource"} == names
    # new_resource should have only_b > 0 and count_a == 0
    for r in res.resources:
        if r.name == "new_resource":
            assert r.count_a == 0 and r.count_b > 0 and r.only_b == r.count_b
    # totals should be consistent sums
    sum_only_a = sum(r.only_a for r in res.resources)
    sum_only_b = sum(r.only_b for r in res.resources)
    sum_overlap = sum(r.overlap for r in res.resources)
    assert res.total_only_a == sum_only_a
    assert res.total_only_b == sum_only_b
    assert res.total_overlap == sum_overlap
