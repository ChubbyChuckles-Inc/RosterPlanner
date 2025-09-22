"""Database Rebuild Utility (Milestone 3.8)

Performs a full rebuild of the database contents from a directory of HTML
assets. Steps:
 1. Drop domain + provenance tables (safe FK order)
 2. Re-apply baseline schema
 3. Apply pending migrations
 4. Run full ingest

Designed for manual recovery and developer tooling. GUI layer may wrap this
with progress reporting in a future milestone (3.8.1).
"""

from __future__ import annotations

from pathlib import Path
import sqlite3
from typing import Iterable

from .schema import apply_schema
from .migration_manager import apply_pending_migrations
from .ingest import ingest_path, IngestReport

__all__ = ["rebuild_database"]

DOMAIN_TABLES = [
    # Children first (FK dependencies)
    "availability",
    "match",
    "player",
    "team",
    "division",
    # Provenance / support tables
    "ingest_provenance",
]


def _drop_tables(conn: sqlite3.Connection, tables: Iterable[str]) -> None:
    for t in tables:
        conn.execute(f"DROP TABLE IF EXISTS {t}")


def rebuild_database(
    conn: sqlite3.Connection,
    html_root: str | Path,
    parser_version: str = "v1",
) -> IngestReport:
    """Drop & recreate schema then ingest all recognized HTML.

    Returns the `IngestReport` from ingest phase. Operates inside a transaction
    for destructive steps; ingest occurs after commit so partial data can be
    inspected if an ingest failure occurs.
    """
    root = Path(html_root)
    if not root.exists():
        raise FileNotFoundError(f"HTML root does not exist: {root}")

    with conn:
        _drop_tables(conn, DOMAIN_TABLES)
        apply_schema(conn)
        apply_pending_migrations(conn)
    report = ingest_path(conn, root, parser_version=parser_version)
    return report
