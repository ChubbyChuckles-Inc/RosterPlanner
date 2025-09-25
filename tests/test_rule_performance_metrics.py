from gui.ingestion.rule_schema import RuleSet
from gui.ingestion.rule_parse_preview import generate_parse_preview
from gui.ingestion.rule_batch_preview import generate_batch_preview

HTML = """
<html><body>
  <table class='ranking'>
    <tr><th>Team</th><th>Pts</th></tr>
    <tr><td>A</td><td>10</td></tr>
  </table>
  <div class='roster'>
    <div class='player'><span class='name'>Alice</span><span class='pts'>11</span></div>
  </div>
</body></html>
"""

RULES = RuleSet.from_mapping(
    {
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
                "fields": {"name": ".name", "points": ".pts"},
            },
        }
    }
)


def test_single_file_performance_metrics():
    preview = generate_parse_preview(RULES, HTML, apply_transforms=False, capture_performance=True)
    assert preview.parse_time_ms >= 0.0
    assert preview.node_count > 0
    assert preview.memory_delta_kb >= 0.0


def test_batch_file_performance_metrics():
    batch = generate_batch_preview(
        RULES,
        {"one.html": HTML, "two.html": HTML},
        apply_transforms=False,
        capture_performance=True,
    )
    assert batch.total_parse_time_ms >= 0.0
    assert batch.total_node_count > 0
    assert batch.peak_memory_kb >= 0.0
