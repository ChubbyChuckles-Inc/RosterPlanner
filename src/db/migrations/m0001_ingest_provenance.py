"""Migration 0001: Add ingest_provenance table.

Tracks ingestion provenance of HTML sources (future roadmap 3.3.2 alignment).
"""

from __future__ import annotations
import sqlite3

MIGRATION_ID = 1
description = "Add ingest_provenance table"

DDL = """
CREATE TABLE IF NOT EXISTS ingest_provenance (
    provenance_id INTEGER PRIMARY KEY,
    source_file TEXT NOT NULL,
    parser_version TEXT,
    ingested_at TEXT DEFAULT CURRENT_TIMESTAMP,
    hash TEXT,
    UNIQUE(source_file, hash)
);
""".strip()


def upgrade(conn: sqlite3.Connection) -> None:
    conn.execute(DDL)
