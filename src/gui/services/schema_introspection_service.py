"""Schema Introspection Service (Milestone 7.11.2).

This module exposes a cached, read-only snapshot of the active SQLite
schema. It powers the Database panel (Milestone 7.11) by providing:

* Table listing (optionally excluding SQLite internal tables)
* Column metadata (type, nullability, default, PK ordering)
* Foreign key relationships (referenced table/column + actions)
* Index metadata (unique flag + ordered column list)
* Row counts (computed once per refresh and cached)

Calls gracefully degrade to empty results if no SQLite connection is
registered; this keeps the GUI resilient during early startup or headless
tests. Consumers should call :meth:`refresh` after operations that mutate
the schema or table contents to keep the cache current.
"""

from __future__ import annotations

from dataclasses import dataclass
from time import monotonic
from threading import RLock
from typing import Dict, List, Optional, Tuple
import sqlite3

__all__ = [
    "ColumnInfo",
    "ForeignKeyInfo",
    "IndexInfo",
    "TableInfo",
    "ColumnStats",
    "SchemaIntrospectionService",
]


@dataclass(frozen=True)
class ColumnInfo:
    """Describes a single column within a table."""

    name: str
    type: str
    not_null: bool
    default: Optional[str]
    pk_position: int

    @property
    def is_primary_key(self) -> bool:
        """Return True when the column participates in the primary key."""

        return self.pk_position > 0


@dataclass(frozen=True)
class ForeignKeyInfo:
    """Represents a foreign key constraint on a table."""

    constraint_id: int
    sequence: int
    column: str
    ref_table: str
    ref_column: str
    on_update: str
    on_delete: str
    match: str

    @property
    def grouping_key(self) -> tuple[int, str]:
        """Return a stable key to group composite foreign keys.

        SQLite's ``PRAGMA foreign_key_list`` returns one row per column and
        associates multi-column foreign keys via a shared ``id``. The
        ``sequence`` value indicates the column ordering. Consumers can group
        rows by ``constraint_id`` to reconstruct composite key relationships.
        """

        return (self.constraint_id, self.ref_table)


@dataclass(frozen=True)
class IndexInfo:
    """Represents an index defined on a table."""

    name: str
    unique: bool
    columns: List[str]


@dataclass(frozen=True)
class TableInfo:
    """Aggregated metadata for a table."""

    name: str
    columns: List[ColumnInfo]
    primary_key: List[str]
    foreign_keys: List[ForeignKeyInfo]
    indexes: List[IndexInfo]
    row_count: Optional[int]
    approx_page_count: Optional[int] = None
    approx_size_bytes: Optional[int] = None
    last_ingested_at: Optional[str] = None


@dataclass(frozen=True)
class ColumnStats:
    """Statistical sample for a column."""

    sample_rows: Optional[int]
    distinct_count: Optional[int]
    null_fraction: Optional[float]
    min_value: Optional[str]
    max_value: Optional[str]


class SchemaIntrospectionService:
    """Read-only helper around SQLite PRAGMA statements.

    The service materializes the schema snapshot on first use (or when
    explicitly refreshed) and serves cached metadata thereafter. This
    minimizes repeated PRAGMA calls while keeping the Database panel
    responsive.
    """

    def __init__(
        self,
        conn: sqlite3.Connection | None,
        *,
        include_internal: bool = False,
        sample_limit: int = 500,
    ) -> None:
        self._conn = conn
        self._include_internal = include_internal
        self._lock = RLock()
        self._tables: Dict[str, TableInfo] = {}
        self._table_order: List[str] = []
        self._page_size: Optional[int] = None
        self._last_ingest: Optional[str] = None
        self._column_stats_cache: Dict[str, Tuple[float, Dict[str, ColumnStats]]] = {}
        self._sample_limit = max(1, sample_limit)

    # ------------------------------------------------------------------
    # Public API
    def list_tables(self) -> List[str]:
        """Return the cached table names (refreshing if necessary)."""

        with self._lock:
            if not self._tables:
                self._refresh_locked()
            return list(self._table_order)

    def get_table_info(self, table: str) -> TableInfo | None:
        """Return cached metadata for *table* (refreshing if required)."""

        if not table:
            return None
        with self._lock:
            if not self._tables:
                self._refresh_locked()
            return self._tables.get(table)

    def describe_all(self) -> Dict[str, TableInfo]:
        """Return a snapshot mapping of table name to :class:`TableInfo`."""

        with self._lock:
            if not self._tables:
                self._refresh_locked()
            return dict(self._tables)

    def refresh(self) -> None:
        """Rebuild the schema cache from the underlying connection."""

        with self._lock:
            self._refresh_locked()

    def invalidate(self) -> None:
        """Clear the cached snapshot. Next access will trigger a refresh."""

        with self._lock:
            self._tables.clear()
            self._table_order.clear()
            self._page_size = None
            self._last_ingest = None
            self._column_stats_cache.clear()

    def get_column_stats(self, table: str, *, max_age_s: float = 30.0) -> Dict[str, ColumnStats]:
        """Return sampled statistics for each column in *table*.

        Results are cached for ``max_age_s`` seconds to avoid repeated scans.
        """

        if not table:
            return {}
        now = monotonic()
        with self._lock:
            cached = self._column_stats_cache.get(table)
            if cached and (now - cached[0] <= max_age_s):
                return dict(cached[1])
        info = self.get_table_info(table)
        if info is None or self._conn is None:
            return {}
        stats: Dict[str, ColumnStats] = {}
        for column in info.columns:
            stats[column.name] = self._sample_column_stats(self._conn, table, column)
        with self._lock:
            self._column_stats_cache[table] = (monotonic(), stats)
        return dict(stats)

    # ------------------------------------------------------------------
    # Internal helpers
    def _refresh_locked(self) -> None:
        if self._conn is None:
            self._tables = {}
            self._table_order = []
            return
        try:
            names = self._fetch_table_names(self._conn)
        except Exception:
            self._tables = {}
            self._table_order = []
            return
        self._page_size = self._load_page_size(self._conn)
        self._last_ingest = self._load_last_ingest(self._conn)
        tables: Dict[str, TableInfo] = {}
        for name in names:
            info = self._build_table_info(self._conn, name)
            if info:
                tables[name] = info
        self._tables = tables
        self._table_order = list(tables.keys())

    def _fetch_table_names(self, conn: sqlite3.Connection) -> List[str]:
        cur = conn.execute(
            "SELECT name FROM sqlite_master WHERE type IN ('table','view') ORDER BY name"
        )
        names = [row[0] for row in cur.fetchall()]
        if not self._include_internal:
            names = [name for name in names if not name.startswith("sqlite_")]
        return names

    def _build_table_info(self, conn: sqlite3.Connection, table: str) -> TableInfo | None:
        columns = self._load_columns(conn, table)
        if not columns:
            return None
        fks = self._load_foreign_keys(conn, table)
        indexes = self._load_indexes(conn, table)
        primary_key = [
            col.name for col in sorted(columns, key=lambda c: c.pk_position) if col.pk_position
        ]
        row_count = self._load_row_count(conn, table)
        page_count, approx_bytes = self._load_table_storage_metrics(conn, table)
        return TableInfo(
            name=table,
            columns=columns,
            primary_key=primary_key,
            foreign_keys=fks,
            indexes=indexes,
            row_count=row_count,
            approx_page_count=page_count,
            approx_size_bytes=approx_bytes,
            last_ingested_at=self._last_ingest,
        )

    # Individual loaders ------------------------------------------------
    def _load_columns(self, conn: sqlite3.Connection, table: str) -> List[ColumnInfo]:
        cur = conn.execute(f"PRAGMA table_info({self._quote_ident(table)})")
        columns: List[ColumnInfo] = []
        for _cid, name, ctype, notnull, default_val, pk in cur.fetchall():
            columns.append(
                ColumnInfo(
                    name=name,
                    type=ctype or "",
                    not_null=bool(notnull),
                    default=None if default_val is None else str(default_val),
                    pk_position=int(pk or 0),
                )
            )
        return columns

    def _load_foreign_keys(self, conn: sqlite3.Connection, table: str) -> List[ForeignKeyInfo]:
        cur = conn.execute(f"PRAGMA foreign_key_list({self._quote_ident(table)})")
        records = cur.fetchall()
        out: List[ForeignKeyInfo] = []
        for (
            constraint_id,
            sequence,
            ref_table,
            from_col,
            ref_col,
            on_update,
            on_delete,
            match,
        ) in records:
            out.append(
                ForeignKeyInfo(
                    constraint_id=int(constraint_id),
                    sequence=int(sequence),
                    column=from_col,
                    ref_table=ref_table,
                    ref_column=ref_col,
                    on_update=on_update,
                    on_delete=on_delete,
                    match=match,
                )
            )
        return out

    def _load_indexes(self, conn: sqlite3.Connection, table: str) -> List[IndexInfo]:
        cur = conn.execute(f"PRAGMA index_list({self._quote_ident(table)})")
        indexes: List[IndexInfo] = []
        for _seq, name, unique, _origin, _partial in cur.fetchall():
            try:
                icur = conn.execute(f"PRAGMA index_info({self._quote_ident(name)})")
                cols = [row[2] for row in icur.fetchall()]
            except Exception:
                cols = []
            indexes.append(IndexInfo(name=name, unique=bool(unique), columns=cols))
        indexes.sort(key=lambda idx: idx.name)
        return indexes

    def _load_row_count(self, conn: sqlite3.Connection, table: str) -> Optional[int]:
        ident = table.replace('"', '""')
        try:
            cur = conn.execute(f'SELECT COUNT(*) FROM "{ident}"')
            row = cur.fetchone()
            return int(row[0]) if row else 0
        except Exception:
            return None

    def _load_table_storage_metrics(
        self, conn: sqlite3.Connection, table: str
    ) -> Tuple[Optional[int], Optional[int]]:
        total_bytes: Optional[int] = None
        queries = [
            "SELECT sum(pgsize) FROM dbstat WHERE name=?",
            "SELECT sum(pgsize) FROM dbstat('main') WHERE name=?",
        ]
        for sql in queries:
            try:
                cur = conn.execute(sql, (table,))
                row = cur.fetchone()
                if row and row[0] is not None:
                    total_bytes = int(row[0])
                    break
            except Exception:
                continue
        if total_bytes is None or total_bytes <= 0:
            return None, None
        page_size = self._page_size or self._load_page_size(conn)
        if page_size:
            pages = max(1, (total_bytes + page_size - 1) // page_size)
        else:
            pages = None
        return pages, total_bytes

    def _sample_column_stats(
        self, conn: sqlite3.Connection, table: str, column: ColumnInfo
    ) -> ColumnStats:
        ident_table = table.replace('"', '""')
        column_ident = column.name.replace('"', '""')
        column_ref = f'"{column_ident}"'
        sql = (
            f"SELECT COUNT(*) AS sample_rows, "
            f"SUM(CASE WHEN {column_ref} IS NULL THEN 1 ELSE 0 END) AS null_count, "
            f"COUNT(DISTINCT {column_ref}) AS distinct_count, "
            f"MIN({column_ref}) AS min_value, "
            f"MAX({column_ref}) AS max_value "
            f'FROM (SELECT {column_ref} FROM "{ident_table}" LIMIT ?)'
        )
        try:
            cur = conn.execute(sql, (self._sample_limit,))
            row = cur.fetchone()
        except Exception:
            return ColumnStats(None, None, None, None, None)
        if not row or row[0] is None:
            return ColumnStats(None, None, None, None, None)
        sample_rows = int(row[0]) if row[0] is not None else None
        if sample_rows == 0:
            return ColumnStats(0, 0, None, None, None)
        null_count = int(row[1]) if row[1] is not None else 0
        distinct_count = int(row[2]) if row[2] is not None else None
        null_fraction = (null_count / sample_rows) * 100 if sample_rows else None
        min_value = str(row[3]) if row[3] is not None else None
        max_value = str(row[4]) if row[4] is not None else None
        if not self._supports_min_max(column.type):
            min_value = None
            max_value = None
        return ColumnStats(sample_rows, distinct_count, null_fraction, min_value, max_value)

    def _load_page_size(self, conn: sqlite3.Connection) -> Optional[int]:
        try:
            row = conn.execute("PRAGMA page_size").fetchone()
            if row and row[0]:
                return int(row[0])
        except Exception:
            return None
        return None

    def _load_last_ingest(self, conn: sqlite3.Connection) -> Optional[str]:
        queries = (
            "SELECT ingested_at FROM provenance_summary ORDER BY ingested_at DESC LIMIT 1",
            "SELECT last_ingested_at FROM provenance ORDER BY last_ingested_at DESC LIMIT 1",
        )
        for sql in queries:
            try:
                cur = conn.execute(sql)
                row = cur.fetchone()
                if row and row[0]:
                    value = str(row[0]).strip()
                    if value:
                        return value
            except Exception:
                continue
        return None

    @staticmethod
    def _supports_min_max(column_type: str | None) -> bool:
        if not column_type:
            return False
        normalized = column_type.strip().upper()
        numeric_tokens = (
            "INT",
            "REAL",
            "NUMERIC",
            "DEC",
            "DOUBLE",
            "FLOAT",
        )
        datetime_tokens = ("DATE", "TIME")
        return any(token in normalized for token in numeric_tokens + datetime_tokens)

    @staticmethod
    def _quote_ident(value: str) -> str:
        """Return an identifier safe for interpolation into PRAGMA statements."""

        escaped = value.replace("'", "''")
        return f"'{escaped}'"
