"""Migration Manager (Milestone 3.2 / 3.2.1)

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

Checksum Verification (3.2.1):
Each migration's upgrade function source code is hashed (SHA256) and stored in
`migration_checksums` table. On subsequent runs, any drift (different hash for
an already applied migration id) is reported via `verify_migration_checksums`.
This helps detect accidental in-place edits of historical migrations.
"""

from __future__ import annotations
import inspect
import hashlib
import sqlite3
from typing import List, Tuple, Dict
from .migrations import discover_migrations

MIGRATION_VERSION_KEY = "migration_version"
CHECKSUM_TABLE_DDL = (
    "CREATE TABLE IF NOT EXISTS migration_checksums ("
    " migration_id INTEGER PRIMARY KEY,"
    " checksum TEXT NOT NULL"
    ")"
)


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


def _ensure_checksum_table(conn: sqlite3.Connection) -> None:
    conn.execute(CHECKSUM_TABLE_DDL)


def _hash_migration(fn) -> str:
    try:
        src = inspect.getsource(fn)
    except OSError:
        # Fallback: repr of function object
        src = repr(fn)
    return hashlib.sha256(src.encode("utf-8")).hexdigest()


def _get_stored_checksums(conn: sqlite3.Connection) -> Dict[int, str]:
    cur = conn.cursor()
    cur.execute("SELECT migration_id, checksum FROM migration_checksums")
    return {int(r[0]): r[1] for r in cur.fetchall()}


def verify_migration_checksums(conn: sqlite3.Connection) -> List[Tuple[int, str, str]]:
    """Return list of (migration_id, expected_checksum, found_checksum) mismatches.

    Only considers migrations whose checksums have already been stored (i.e., applied).
    New migrations not yet applied are ignored.
    """
    migrations = discover_migrations()
    stored = _get_stored_checksums(conn)
    mismatches: List[Tuple[int, str, str]] = []
    for mid, _desc, fn in migrations:
        if mid not in stored:
            continue
        current_hash = _hash_migration(fn)
        if current_hash != stored[mid]:
            mismatches.append((mid, stored[mid], current_hash))
    return mismatches


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
            _ensure_checksum_table(conn)
            for mid, desc, fn in pending:
                fn(conn)
                # Store checksum after successful apply
                checksum = _hash_migration(fn)
                conn.execute(
                    "INSERT OR REPLACE INTO migration_checksums(migration_id, checksum) VALUES(?,?)",
                    (mid, checksum),
                )
                _set_current_version(conn, mid)
    except Exception:
        raise
    return result_meta


__all__ = ["apply_pending_migrations", "verify_migration_checksums"]
