from gui.ingestion.rule_schema import RuleSet
from gui.ingestion.selector_watchlist_store import (
    SelectorWatchEntry,
    compute_watchlist_drift,
)

HTML = {
    "team": """
    <html><body>
      <div class='roster'>
        <div class='player'><span class='name'>Alice</span></div>
        <div class='player'><span class='name'>Bob</span></div>
      </div>
      <table class='ranking'>
        <tr><th>Team</th></tr>
        <tr><td>X</td></tr>
        <tr><td>Y</td></tr>
      </table>
    </body></html>
    """,
}


RULES = RuleSet.from_mapping(
    {
        "resources": {
            "team_roster": {
                "kind": "list",
                "selector": "div.roster",
                "item_selector": "div.player",
                "fields": {"name": {"selector": ".name"}},
            },
            "ranking": {
                "kind": "table",
                "selector": "table.ranking",
                "columns": ["team"],
            },
        }
    }
)


def test_watchlist_field_ok():
    entry = SelectorWatchEntry(
        resource="team_roster",
        target_type="field",
        target_name="name",
        baseline_count=2,
        threshold_percent=50,
    )
    results = compute_watchlist_drift(RULES, [entry], HTML)
    res = results[entry.identifier()]
    assert res.current_count == 2
    assert not res.alert
    assert res.drop_percent == 0.0


def test_watchlist_drop_triggers_alert():
    entry = SelectorWatchEntry(
        resource="team_roster",
        target_type="field",
        target_name="name",
        baseline_count=4,
        threshold_percent=25,
    )
    results = compute_watchlist_drift(RULES, [entry], HTML)
    res = results[entry.identifier()]
    assert res.alert
    assert res.drop_percent == 50.0


def test_watchlist_zero_alert():
    entry = SelectorWatchEntry(
        resource="ranking",
        target_type="root",
        baseline_count=1,
        threshold_percent=50,
    )
    html_zero = {"team": "<html><body></body></html>"}
    results = compute_watchlist_drift(RULES, [entry], html_zero)
    res = results[entry.identifier()]
    assert res.alert
    assert res.current_count == 0
    assert res.drop_percent == 100.0 or res.reason in ("", None)
