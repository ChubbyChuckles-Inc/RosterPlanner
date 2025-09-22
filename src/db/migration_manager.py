"""Migration Manager (Milestone 3.2)

Applies pending migrations in order. Uses `schema_meta` table with key 'migration_version'.

Public API:
- apply_pending_migrations(conn, dry_run=False) -> list[tuple[int,str]] of applied or pending migrations.

Behavior:
- Discovers migrations via db.migrations.discover_migrations().
- Reads current migration_version (defaults 0 if missing).
- Filters migrations with id > current.
- If dry_run: returns list without applying.
- Else: applies each in a single overall transaction (all-or-nothing) updating migration_version after each apply.

Idempotency: Re-running when no pending migrations returns empty list.
"""

from __future__ import annotations
import sqlite3
from typing import List, Tuple
from .migrations import discover_migrations

MIGRATION_VERSION_KEY = "migration_version"


def _get_current_version(conn: sqlite3.Connection) -> int:
    cur = conn.cursor()
    cur.execute("SELECT value FROM schema_meta WHERE key=?", (MIGRATION_VERSION_KEY,))
    row = cur.fetchone()
    if not row:
        return 0
    try:
        return int(row[0])
    except ValueError:
        return 0


def _set_current_version(conn: sqlite3.Connection, version: int) -> None:
    conn.execute(
        "INSERT OR REPLACE INTO schema_meta(key,value) VALUES(?,?)",
        (MIGRATION_VERSION_KEY, str(version)),
    )


def apply_pending_migrations(
    conn: sqlite3.Connection, dry_run: bool = False
) -> List[Tuple[int, str]]:
    migrations = discover_migrations()
    current = _get_current_version(conn)
    pending = [(mid, desc, fn) for (mid, desc, fn) in migrations if mid > current]
    result_meta: List[Tuple[int, str]] = [(mid, desc) for (mid, desc, _fn) in pending]
    if dry_run or not pending:
        return result_meta
    try:
        with conn:  # transactional context
            for mid, desc, fn in pending:
                fn(conn)
                _set_current_version(conn, mid)
    except Exception:
        # Transaction context will roll back automatically
        raise
    return result_meta


__all__ = ["apply_pending_migrations"]
