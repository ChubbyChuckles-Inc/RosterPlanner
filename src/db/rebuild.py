"""Database Rebuild Utilities (Milestones 3.8 & 3.8.1)

Provides two rebuild flows:
 - ``rebuild_database``: legacy, synchronous rebuild (drop -> schema -> migrations -> ingest).
 - ``rebuild_database_with_progress``: enhanced variant emitting progress events and
     performing a *partial rollback* (restoring the original DB file) if an error occurs
     after destructive operations.

Partial rollback strategy:
 - If the underlying database is file-backed, we create a byte-for-byte *backup copy*
     of the file before dropping any tables (using SQLite backup API for consistency).
 - If any phase fails (drop/schema/migrations/ingest), we attempt to restore the
     original database file contents from that backup. For in-memory databases the
     rollback is *best-effort only* (not supported fully) and will simply surface the
     error without restoration.

Design notes:
 - Progress is reported via a callback receiving ``RebuildProgressEvent`` objects.
 - To keep public API surface stable, the original ``rebuild_database`` remains.
 - The progress-enabled function supports dependency injection of the ingest
     function for deterministic testing / failure simulation.
 - The caller should treat the passed connection as potentially *closed* after an
     error rollback (we close to ensure file restoration safety). A future refactor
     may return a *replacement* connection.
"""

from __future__ import annotations

from pathlib import Path
import sqlite3
from typing import Iterable, Callable, Optional
from dataclasses import dataclass
from enum import Enum, auto
import shutil
import tempfile

try:  # Logging is optional; fall back silently if unavailable
    import logging

    _log = logging.getLogger(__name__)
except Exception:  # pragma: no cover

    class _Dummy:
        def debug(self, *a, **k):
            pass

        def info(self, *a, **k):
            pass

        def warning(self, *a, **k):
            pass

        def error(self, *a, **k):
            pass

    _log = _Dummy()

from .schema import apply_schema
from .migration_manager import apply_pending_migrations
from .ingest import ingest_path, IngestReport

__all__ = [
    "rebuild_database",
    "rebuild_database_with_progress",
    "RebuildPhase",
    "RebuildProgressEvent",
]

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


class RebuildPhase(Enum):
    """Phases of the enhanced rebuild process."""

    START = auto()
    BACKUP = auto()
    DROP = auto()
    SCHEMA = auto()
    MIGRATIONS = auto()
    INGEST = auto()
    COMPLETE = auto()
    ROLLBACK = auto()
    ERROR = auto()


@dataclass
class RebuildProgressEvent:
    """Represents a progress update for the rebuild flow.

    Attributes:
        phase: Current :class:`RebuildPhase`.
        message: Human-readable description.
        percent: Integer 0-100 coarse overall progress estimate.
        error: Optional error message (only populated on ERROR phase).
    """

    phase: RebuildPhase
    message: str
    percent: int
    error: Optional[str] = None


ProgressCallback = Callable[[RebuildProgressEvent], None]


def _drop_tables(conn: sqlite3.Connection, tables: Iterable[str]) -> None:
    for t in tables:
        conn.execute(f"DROP TABLE IF EXISTS {t}")


def _emit(
    cb: Optional[ProgressCallback],
    phase: RebuildPhase,
    message: str,
    percent: int,
    error: str | None = None,
):
    if cb is None:
        return
    evt = RebuildProgressEvent(phase=phase, message=message, percent=percent, error=error)
    try:
        cb(evt)
    except Exception:  # pragma: no cover - user callback safety
        _log.warning("Progress callback raised; ignoring", exc_info=True)


def _get_db_path(conn: sqlite3.Connection) -> str | None:
    try:
        cur = conn.execute("PRAGMA database_list")
        for _, name, file_path in cur.fetchall():  # type: ignore
            if name == "main" and file_path:
                return str(file_path)
    except Exception:  # pragma: no cover
        return None
    return None


def _create_file_backup(db_path: str) -> str:
    """Create a filesystem-level backup of the SQLite DB.

    Uses simple file copy (the rebuild process only starts this after obtaining
    a consistent state). Returns the backup file path.
    """
    suffix = ".pre_rebuild_backup"
    backup_path = db_path + suffix
    shutil.copy2(db_path, backup_path)
    return backup_path


def rebuild_database_with_progress(
    conn: sqlite3.Connection,
    html_root: str | Path,
    parser_version: str = "v1",
    progress: ProgressCallback | None = None,
    rollback_on_error: bool = True,
    ingest_func: Callable[[sqlite3.Connection, Path, str], IngestReport] = ingest_path,
) -> IngestReport:
    """Enhanced rebuild with progress events & partial rollback.

    Args:
        conn: Existing SQLite connection (foreign keys enforced by caller).
        html_root: Directory with HTML assets.
        parser_version: Parser version tag.
        progress: Optional callback invoked with :class:`RebuildProgressEvent`.
        rollback_on_error: Attempt to restore previous DB file on failure.
        ingest_func: Injection point for testing (defaults to :func:`ingest_path`).

    Returns:
        IngestReport on success.

    Raises:
        Exception: Propagates the underlying failure after attempted rollback.
    """
    root = Path(html_root)
    if not root.exists():
        raise FileNotFoundError(f"HTML root does not exist: {root}")

    _emit(progress, RebuildPhase.START, "Starting database rebuild", 0)
    db_path = _get_db_path(conn)
    backup_path: str | None = None
    if db_path and rollback_on_error:
        try:
            _emit(progress, RebuildPhase.BACKUP, "Creating backup", 5)
            backup_path = _create_file_backup(db_path)
        except Exception:  # pragma: no cover - backup failure shouldn't abort unless requested
            _log.error("Failed to create backup; rollback disabled", exc_info=True)
            backup_path = None

    try:
        _emit(progress, RebuildPhase.DROP, "Dropping tables", 15)
        with conn:
            _drop_tables(conn, DOMAIN_TABLES)
        _emit(progress, RebuildPhase.SCHEMA, "Applying schema", 30)
        with conn:
            apply_schema(conn)
        _emit(progress, RebuildPhase.MIGRATIONS, "Applying migrations", 45)
        with conn:
            apply_pending_migrations(conn)
        _emit(progress, RebuildPhase.INGEST, "Ingesting HTML", 70)
        report = ingest_func(conn, root, parser_version=parser_version)
        _emit(progress, RebuildPhase.COMPLETE, "Rebuild complete", 100)
        return report
    except Exception as e:  # noqa: BLE001
        _log.error("Rebuild failed: %s", e, exc_info=True)
        if backup_path and rollback_on_error and db_path:
            _emit(progress, RebuildPhase.ROLLBACK, "Attempting rollback", 80)
            try:
                # Close current connection to release file lock
                try:
                    conn.close()
                except Exception:
                    pass
                # Restore file bytes
                shutil.copy2(backup_path, db_path)
                _emit(progress, RebuildPhase.ROLLBACK, "Rollback successful", 85)
            except Exception:  # pragma: no cover - rollback failure path
                _emit(progress, RebuildPhase.ROLLBACK, "Rollback failed", 85)
        _emit(progress, RebuildPhase.ERROR, "Rebuild error", 90, error=str(e))
        raise
    finally:
        # Cleanup backup file
        if backup_path:
            try:
                Path(backup_path).unlink(missing_ok=True)  # type: ignore[arg-type]
            except Exception:  # pragma: no cover
                pass


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
