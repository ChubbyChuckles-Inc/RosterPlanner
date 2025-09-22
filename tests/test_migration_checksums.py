from __future__ import annotations
import sqlite3
import importlib
from db.schema import apply_schema
from db.migration_manager import (
    apply_pending_migrations,
    verify_migration_checksums,
    MIGRATION_VERSION_KEY,
)


def test_checksums_recorded_after_apply():
    conn = sqlite3.connect(":memory:")
    conn.execute("PRAGMA foreign_keys=ON")
    apply_schema(conn)
    apply_pending_migrations(conn)
    cur = conn.cursor()
    cur.execute("SELECT COUNT(*) FROM migration_checksums")
    count = cur.fetchone()[0]
    assert count >= 1


def test_checksum_mismatch_detection(monkeypatch):
    conn = sqlite3.connect(":memory:")
    conn.execute("PRAGMA foreign_keys=ON")
    apply_schema(conn)
    apply_pending_migrations(conn)
    # Monkeypatch migration function source to simulate drift
    import db.migrations.m0001_ingest_provenance as m0001

    original_upgrade = m0001.upgrade

    def fake_upgrade(conn):  # pragma: no cover - executed only for checksum hashing
        # altered body
        pass

    monkeypatch.setattr(m0001, "upgrade", fake_upgrade)
    mismatches = verify_migration_checksums(conn)
    assert any(mid == m0001.MIGRATION_ID for (mid, _expected, _found) in mismatches)
    # Restore to avoid side effects
    monkeypatch.setattr(m0001, "upgrade", original_upgrade)
