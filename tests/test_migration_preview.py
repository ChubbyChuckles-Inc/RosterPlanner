from __future__ import annotations
import sqlite3
from db.schema import apply_schema
from db.migration_manager import preview_pending_migration_sql, apply_pending_migrations


def test_preview_returns_sql_statements_for_pending():
    conn = sqlite3.connect(":memory:")
    conn.execute("PRAGMA foreign_keys=ON")
    apply_schema(conn)
    preview = preview_pending_migration_sql(conn)
    assert preview, "Expected at least one pending migration in preview"
    # Each entry: (id, desc, statements)
    mid, desc, stmts = preview[0]
    assert isinstance(mid, int)
    assert isinstance(desc, str)
    assert any("CREATE TABLE" in s for s in stmts)


def test_preview_empty_after_apply():
    conn = sqlite3.connect(":memory:")
    conn.execute("PRAGMA foreign_keys=ON")
    apply_schema(conn)
    apply_pending_migrations(conn)
    preview = preview_pending_migration_sql(conn)
    assert preview == []
