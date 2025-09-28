from gui.ingestion.rule_example_sampler import ExampleRow, generate_example_rows
from gui.ingestion.rule_schema import RuleSet


def _collect(rows, field):
    return [row for row in rows if row.field == field]


def test_generate_example_rows_for_transforms():
    mapping = {
        "version": 1,
        "resources": {
            "players": {
                "kind": "list",
                "selector": "div.player",
                "item_selector": "div.row",
                "fields": {
                    "name": {
                        "selector": "span.name",
                        "transforms": [{"kind": "trim"}, {"kind": "collapse_ws"}],
                    },
                    "rating": {
                        "selector": "span.rating",
                        "transforms": [{"kind": "trim"}, {"kind": "to_number"}],
                    },
                    "joined": {
                        "selector": "span.joined",
                        "transforms": [
                            {
                                "kind": "parse_date",
                                "formats": ["%d.%m.%Y", "%Y-%m-%d"],
                            }
                        ],
                    },
                },
            }
        },
    }
    rule_set = RuleSet.from_mapping(mapping)
    samples = generate_example_rows(rule_set, max_samples_per_field=4)
    assert "players" in samples
    rows = samples["players"]

    rating_rows = _collect(rows, "rating")
    assert any(row.normalized in {"1234", "1234.0"} for row in rating_rows)
    assert any(row.is_outlier for row in rating_rows)

    joined_rows = _collect(rows, "joined")
    assert any(row.normalized == "2024-03-12" for row in joined_rows)

    name_rows = _collect(rows, "name")
    assert any("collapse_ws" in row.note for row in name_rows)


def test_generate_example_rows_for_table_columns():
    mapping = {
        "version": 1,
        "resources": {
            "standings": {
                "kind": "table",
                "selector": "table.standings",
                "columns": ["team", "wins", "losses", "points"],
            }
        },
    }
    rule_set = RuleSet.from_mapping(mapping)
    samples = generate_example_rows(rule_set, max_samples_per_field=2)

    assert "standings" in samples
    rows = samples["standings"]
    assert len(rows) == 2
    assert all(isinstance(row, ExampleRow) for row in rows)
    assert all(row.note.startswith("table column") for row in rows)
    assert not any(row.is_outlier for row in rows)
