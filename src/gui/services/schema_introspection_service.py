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
from threading import RLock
from typing import Dict, Iterable, List, Optional
import sqlite3

__all__ = [
    "ColumnInfo",
    "ForeignKeyInfo",
    "IndexInfo",
    "TableInfo",
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

    column: str
    ref_table: str
    ref_column: str
    on_update: str
    on_delete: str
    match: str


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


class SchemaIntrospectionService:
    """Read-only helper around SQLite PRAGMA statements.

    The service materializes the schema snapshot on first use (or when
    explicitly refreshed) and serves cached metadata thereafter. This
    minimizes repeated PRAGMA calls while keeping the Database panel
    responsive.
    """

    def __init__(self, conn: sqlite3.Connection | None, *, include_internal: bool = False) -> None:
        self._conn = conn
        self._include_internal = include_internal
        self._lock = RLock()
        self._tables: Dict[str, TableInfo] = {}
        self._table_order: List[str] = []

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
        return TableInfo(
            name=table,
            columns=columns,
            primary_key=primary_key,
            foreign_keys=fks,
            indexes=indexes,
            row_count=row_count,
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
        for _id, _seq, ref_table, from_col, ref_col, on_update, on_delete, match in records:
            out.append(
                ForeignKeyInfo(
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

    @staticmethod
    def _quote_ident(value: str) -> str:
        """Return an identifier safe for interpolation into PRAGMA statements."""

        escaped = value.replace("'", "''")
        return f"'{escaped}'"
