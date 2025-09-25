from gui.ingestion.rule_schema import RuleSet
from gui.ingestion.rule_batch_preview import generate_batch_preview

HTML_A = """
<html><body>
  <table class='ranking'>
    <tr><th>Team</th><th>Pts</th></tr>
    <tr><td>A</td><td>10</td></tr>
    <tr><td>B</td><td>12</td></tr>
  </table>
  <div class='roster'>
    <div class='player'><span class='name'> Alice </span><span class='pts'>11</span></div>
    <div class='player'><span class='name'>Bob</span><span class='pts'>  9 </span></div>
  </div>
</body></html>
"""

HTML_B = """
<html><body>
  <table class='ranking'>
    <tr><th>Team</th><th>Pts</th></tr>
    <tr><td>B</td><td>12</td></tr>
    <tr><td>C</td><td>14</td></tr>
  </table>
  <div class='roster'>
    <div class='player'><span class='name'>Bob</span><span class='pts'>  9 </span></div>
    <div class='player'><span class='name'>Carol</span><span class='pts'>13</span></div>
  </div>
</body></html>
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
                    "points": {"selector": ".pts", "transforms": ["trim", {"kind": "to_number"}]},
                },
            },
        },
    }
)


def test_batch_preview_basic_aggregation():
    result = generate_batch_preview(
        RULES,
        {"fileA.html": HTML_A, "fileB.html": HTML_B},
        apply_transforms=True,
    )
    # ranking_table: rows per file (2 + 2) total 4; unique teams A,B,C => 3
    agg_ranking = next(a for a in result.resource_aggregates if a.resource == "ranking_table")
    assert agg_ranking.total_records == 4
    assert agg_ranking.unique_records == 3
    assert agg_ranking.duplicate_records == 1  # team B duplicate

    # team_roster: 2 + 2 total 4; unique players Alice, Bob, Carol => 3, Bob duplicate once
    agg_roster = next(a for a in result.resource_aggregates if a.resource == "team_roster")
    assert agg_roster.total_records == 4
    assert agg_roster.unique_records == 3
    assert agg_roster.duplicate_records == 1

    # File stats shape: 2 files * 2 resources = 4 entries
    assert len(result.file_resource_stats) == 4
    # Check ordering: fileA entries precede fileB entries
    first_two = result.file_resource_stats[:2]
    assert {s.file for s in first_two} == {"fileA.html"}

    # Aggregated record ordering: first occurrence order
    roster_records = result.aggregated_records["team_roster"]
    names = [r["name"] for r in roster_records]
    assert names == ["Alice", "Bob", "Carol"]


def test_batch_preview_empty_input():
    result = generate_batch_preview(RULES, {}, apply_transforms=False)
    # All aggregates zero counts
    for agg in result.resource_aggregates:
        assert agg.total_records == 0
        assert agg.unique_records == 0
        assert agg.duplicate_records == 0
    # No file stats
    assert result.file_resource_stats == []
