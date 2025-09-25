from gui.ingestion.rule_schema import RuleSet
from gui.ingestion.rule_coercion import generate_coercion_preview


def _rules():
    return RuleSet.from_mapping(
        {
            "allow_expressions": True,
            "resources": {
                "players": {
                    "kind": "list",
                    "selector": "div.players",
                    "item_selector": "div.player",
                    "fields": {
                        "name": {"selector": ".name", "transforms": ["trim"]},
                        "score": {
                            "selector": ".score",
                            "transforms": ["trim", {"kind": "to_number"}],
                        },
                        "joined": {
                            "selector": ".joined",
                            "transforms": [
                                {"kind": "parse_date", "formats": ["%Y-%m-%d", "%d.%m.%Y"]}
                            ],
                        },
                    },
                },
                "ranking_table": {
                    "kind": "table",
                    "selector": "table.ranking",
                    "columns": ["team", "points"],
                },
            },
        }
    )


def test_coercion_preview_basic_and_failures():
    rs = _rules()
    samples = {
        "players": {
            "name": ["  Alice  ", "Bob"],
            "score": ["10", "3,5", "abc"],  # 'abc' fails numeric coercion
            "joined": ["2025-01-02", "02.01.2025", "13/07/2025"],  # last fails
        },
        "ranking_table": {"team": ["X", "Y"], "points": ["7", "8"]},
    }
    result = generate_coercion_preview(rs, samples)
    stats_by_field = {(s.resource, s.field): s for s in result.stats}
    # Trim applied
    name_stats = stats_by_field[("players", "name")]
    assert name_stats.success == 2 and not name_stats.failures
    # Numeric coercion: 2 successes, 1 failure
    score_stats = stats_by_field[("players", "score")]
    assert score_stats.success == 2 and score_stats.failures == 1 and score_stats.errors
    # Date coercion: 2 successes, 1 failure
    joined_stats = stats_by_field[("players", "joined")]
    assert joined_stats.success == 2 and joined_stats.failures == 1
    # Table passthrough
    table_points = stats_by_field[("ranking_table", "points")]
    assert table_points.success == 2 and not table_points.failures


def test_coercion_preview_empty_samples():
    rs = _rules()
    result = generate_coercion_preview(rs, {})
    # All fields present but zero totals
    assert all(s.total == 0 for s in result.stats)
