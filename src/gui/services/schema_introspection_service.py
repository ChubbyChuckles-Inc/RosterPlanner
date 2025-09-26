"""Schema Introspection Service (Milestone 7.11.2 early scaffold).

Provides lightweight, read-only SQLite schema inspection used by the
Database Panel (7.11.1+) and later advanced diagnostics. Implemented now
so the initial dock can already show real table & column listings.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import List, Optional, Dict
import sqlite3

__all__ = ["ColumnInfo", "TableInfo", "SchemaIntrospectionService"]


@dataclass(frozen=True)
class ColumnInfo:
    name: str
    type: str
    not_null: bool
    default: Optional[str]
    pk: bool


@dataclass(frozen=True)
class TableInfo:
    name: str
    columns: List[ColumnInfo]


class SchemaIntrospectionService:
    """Read-only helper around SQLite PRAGMA statements.

    Failures are swallowed returning empty results to keep GUI resilient.
    """

    def __init__(self, conn: sqlite3.Connection | None, *, include_internal: bool = False) -> None:
        self._conn = conn
        self._include_internal = include_internal

    def list_tables(self) -> List[str]:
        if self._conn is None:
            return []
        try:
            cur = self._conn.execute(
                "SELECT name FROM sqlite_master WHERE type='table' ORDER BY name"
            )
            names = [r[0] for r in cur.fetchall()]
            if not self._include_internal:
                names = [n for n in names if not n.startswith("sqlite_")]
            return names
        except Exception:
            return []

    def get_table_info(self, table: str) -> TableInfo | None:
        if self._conn is None or not table:
            return None
        try:
            cur = self._conn.execute(f"PRAGMA table_info('{table}')")
            cols: List[ColumnInfo] = []
            for _cid, name, ctype, notnull, default_val, pk in cur.fetchall():
                cols.append(
                    ColumnInfo(
                        name=name,
                        type=ctype or "",
                        not_null=bool(notnull),
                        default=None if default_val is None else str(default_val),
                        pk=bool(pk),
                    )
                )
            if not cols:
                return None
            return TableInfo(name=table, columns=cols)
        except Exception:
            return None

    def describe_all(self) -> Dict[str, TableInfo]:
        out: Dict[str, TableInfo] = {}
        for name in self.list_tables():
            ti = self.get_table_info(name)
            if ti:
                out[name] = ti
        return out
