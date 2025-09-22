"""Migration 0002: Extend ingest_provenance with access tracking.

Adds columns to support eviction policy (Milestone 3.7.1):
 - last_accessed_at (TEXT, defaults CURRENT_TIMESTAMP)
 - access_count (INTEGER, defaults 0)

These allow implementing both time-based (max_age_days) and LRU (max_entries drop least recently accessed) eviction.
"""

from __future__ import annotations
import sqlite3

MIGRATION_ID = 2
description = "Extend ingest_provenance with last_accessed_at + access_count"


def upgrade(conn: sqlite3.Connection) -> None:
    # Add columns if not already present; SQLite supports ADD COLUMN without IF NOT EXISTS for older versions,
    # so we guard by pragma table_info inspection to be idempotent for safety.
    cur = conn.cursor()
    cur.execute("PRAGMA table_info(ingest_provenance)")
    existing_cols = {r[1] for r in cur.fetchall()}
    if "last_accessed_at" not in existing_cols:
        conn.execute(
            "ALTER TABLE ingest_provenance ADD COLUMN last_accessed_at TEXT DEFAULT CURRENT_TIMESTAMP"
        )
    if "access_count" not in existing_cols:
        conn.execute("ALTER TABLE ingest_provenance ADD COLUMN access_count INTEGER DEFAULT 0")
