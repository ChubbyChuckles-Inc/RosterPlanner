import sqlite3

from gui.ingestion.rule_schema import RuleSet
from gui.ingestion.rule_migration import generate_migration_preview


def _rules_single_table():
    # Table rules currently only declare column names (no per-column transforms)
    return RuleSet.from_mapping(
        {
            "resources": {
                "ranking_table": {
                    "kind": "table",
                    "selector": "table.ranking",
                    "columns": ["team", "points"],
                }
            }
        }
    )


def test_generate_migration_preview_create_table():
    rs = _rules_single_table()
    conn = sqlite3.connect(":memory:")
    preview = generate_migration_preview(rs, conn)
    kinds = [a.kind for a in preview.actions]
    assert kinds == ["create_table"]
    sql = preview.actions[0].sql or ""
    assert "CREATE TABLE ranking_table" in sql
    # Both columns default to TEXT (no transforms for table rules)
    assert "team TEXT" in sql and "points TEXT" in sql


def test_generate_migration_preview_add_column_and_type_note():
    rs = _rules_single_table()
    conn = sqlite3.connect(":memory:")
    cur = conn.cursor()
    # Existing table with only 'team' as TEXT
    # Live schema has points REAL while rule expects TEXT -> type mismatch note
    cur.execute("CREATE TABLE ranking_table (team TEXT, points REAL);")
    conn.commit()
    preview = generate_migration_preview(rs, conn)
    # points exists but has unexpected REAL type (rule would create TEXT) -> type_note only
    assert len(preview.actions) == 1
    act = preview.actions[0]
    assert act.kind == "type_note"
    assert act.column == "points"
    assert "mismatch" in (act.note or "")
