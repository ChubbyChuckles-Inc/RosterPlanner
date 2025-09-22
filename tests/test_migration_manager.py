from __future__ import annotations
import sqlite3
from db.schema import apply_schema
from db.migration_manager import apply_pending_migrations, MIGRATION_VERSION_KEY


def _get_migration_version(conn):
    cur = conn.cursor()
    cur.execute("SELECT value FROM schema_meta WHERE key=?", (MIGRATION_VERSION_KEY,))
    row = cur.fetchone()
    return int(row[0]) if row else 0


def test_migrations_apply_on_fresh_db():
    conn = sqlite3.connect(":memory:")
    conn.execute("PRAGMA foreign_keys=ON")
    apply_schema(conn)
    applied = apply_pending_migrations(conn)
    assert applied, "Expected at least one migration to apply"
    version = _get_migration_version(conn)
    assert version == max(mid for mid, _ in applied)
    # Table created by migration exists
    cur = conn.cursor()
    cur.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='ingest_provenance'")
    assert cur.fetchone() is not None


def test_migrations_idempotent_on_second_run():
    conn = sqlite3.connect(":memory:")
    conn.execute("PRAGMA foreign_keys=ON")
    apply_schema(conn)
    first = apply_pending_migrations(conn)
    second = apply_pending_migrations(conn)
    assert first
    assert second == []  # nothing more to apply


def test_dry_run_lists_pending():
    conn = sqlite3.connect(":memory:")
    conn.execute("PRAGMA foreign_keys=ON")
    apply_schema(conn)
    pending = apply_pending_migrations(conn, dry_run=True)
    assert pending  # one pending
    # After real apply, dry run shows empty
    apply_pending_migrations(conn)
    pending_after = apply_pending_migrations(conn, dry_run=True)
    assert pending_after == []
