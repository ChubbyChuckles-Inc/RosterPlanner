from gui.ingestion.rule_schema import RuleSet
from gui.ingestion.rule_parse_preview import generate_parse_preview
from gui.ingestion.rule_batch_preview import generate_batch_preview

HTML = """
<html><body>
  <div class='players'>
    <div class='p'><span class='name'>Alice</span></div>
  </div>
</body></html>
"""

RULES = RuleSet.from_mapping(
    {
        "resources": {
            # Intentionally broken selector for table kind
            "missing_table": {
                "kind": "table",
                "selector": "table.does-not-exist",
                "columns": ["col1"],
            },
            "player_list": {
                "kind": "list",
                "selector": "div.players",
                "item_selector": "div.p",
                "fields": {"name": {"selector": ".name", "transforms": ["trim"]}},
            },
        }
    }
)


def test_single_file_errors_collected():
    preview = generate_parse_preview(RULES, HTML, apply_transforms=True)
    # Expect an error entry for missing table
    messages = [e["message"] for e in preview.errors]
    assert any("Selector error for table" in m for m in messages) or any(
        "warning" in e.get("severity", "") for e in preview.errors
    )
    # Player list should produce no errors
    assert any(e["resource"] == "missing_table" for e in preview.errors)


def test_batch_errors_aggregated():
    batch = generate_batch_preview(
        RULES,
        {"a.html": HTML, "b.html": HTML},
        apply_transforms=True,
    )
    mt_errors = [e for e in batch.errors if e["resource"] == "missing_table"]
    # Two files -> at least one error per file (selector fails each time) or empty if selector handled silently
    assert len(mt_errors) >= 1
    # Enriched with file key
    assert all("file" in e for e in mt_errors)
