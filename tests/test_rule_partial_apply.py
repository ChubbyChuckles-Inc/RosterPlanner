from gui.ingestion.rule_schema import RuleSet
from gui.ingestion.rule_partial_apply import partial_apply


def _sample_ruleset():
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
                "fields": {
                    "name": {"selector": "span.name"},
                    "pz": {"selector": "span.pz"},
                },
            },
        },
    }
    return RuleSet.from_mapping(payload)


def test_partial_apply_basic_insertion():
    rs = _sample_ruleset()
    html_docs = {
        "file1.html": """
        <html><body>
        <table class='ranking'>
            <tr><th>Team</th><th>Pts</th></tr>
            <tr><td>A</td><td>10</td></tr>
            <tr><td>B</td><td>8</td></tr>
        </table>
        <ul class='players'>
            <li><span class='name'>Alice</span><span class='pz'>1400</span></li>
            <li><span class='name'>Bob</span><span class='pz'>1350</span></li>
        </ul>
        </body></html>
        ",
        "file2.html": """
        <html><body>
        <table class='ranking'>
            <tr><th>Team</th><th>Pts</th></tr>
            <tr><td>C</td><td>6</td></tr>
        </table>
        </body></html>
        ",
    }
    result = partial_apply(rs, html_docs, ["ranking", "players"], apply_transforms=False)
    # Expect tables created for both resources
    assert "sandbox_ranking" in result.tables
    assert "sandbox_players" in result.tables
    # Ranking rows: 2 + 1 = 3
    assert result.inserted_rows.get("sandbox_ranking") == 3
    # Players only present in one file
    assert result.inserted_rows.get("sandbox_players") == 2
    # No hard errors expected
    severities = {e.get("severity") for e in result.errors}
    assert not severities or severities <= {"warning"}


def test_partial_apply_ignores_unselected():
    rs = _sample_ruleset()
    html_docs = {
        "file.html": """
        <html><body>
        <table class='ranking'>
            <tr><th>Team</th><th>Pts</th></tr>
            <tr><td>X</td><td>1</td></tr>
        </table>
        </body></html>
        ",
    }
    result = partial_apply(rs, html_docs, ["players"])  # table resource not selected
    # Only players table should exist
    assert "sandbox_players" in result.tables
    assert "sandbox_ranking" not in result.inserted_rows
    # No inserted rows for players (not present)
    assert result.inserted_rows.get("sandbox_players", 0) == 0
