"""Migration Preview (Milestone 7.10.13)

Generates a non-destructive SQL migration preview by diffing the current
SQLite database schema against the schema implied by the active ``RuleSet``.

It DOES NOT execute schema changes – it only returns structured actions the
GUI can render in the Ingestion Lab before the user decides to apply changes.

Action Types
------------
* create_table: table does not exist; includes full CREATE TABLE SQL.
* add_column: column missing; includes ALTER TABLE ... ADD COLUMN SQL.
* type_note: column exists but type differs (informational; SQLite requires
             a rebuild pattern for real type changes – deferred to later).

Design Goals
------------
* Read-only introspection via PRAGMA table_info.
* Reuse existing mapping inference (``rule_mapping``) for field list & types.
* Deterministic ordering (alphabetical by table, then column).
* Pure logic + stdlib only (test friendly).
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import List, Dict, Mapping, Tuple, Optional
import sqlite3

from .rule_schema import RuleSet
from .rule_mapping import build_mapping_entries, group_by_resource, FieldType

__all__ = [
    "MigrationAction",
    "MigrationPreview",
    "generate_migration_preview",
]


# ---------------------------------------------------------------------------
# Data Structures


@dataclass
class MigrationAction:
    kind: str  # create_table | add_column | type_note
    table: str
    column: Optional[str] = None
    sqlite_type: Optional[str] = None
    sql: Optional[str] = None  # suggested statement (for create_table/add_column)
    note: Optional[str] = None

    def to_mapping(self) -> Mapping[str, object]:  # pragma: no cover - trivial
        return {
            "kind": self.kind,
            "table": self.table,
            **({"column": self.column} if self.column else {}),
            **({"sqlite_type": self.sqlite_type} if self.sqlite_type else {}),
            **({"sql": self.sql} if self.sql else {}),
            **({"note": self.note} if self.note else {}),
        }


@dataclass
class MigrationPreview:
    actions: List[MigrationAction]

    def to_mapping(self) -> Mapping[str, object]:  # pragma: no cover - trivial
        return {"actions": [a.to_mapping() for a in self.actions]}


# ---------------------------------------------------------------------------
# Implementation


def _sqlite_type(ftype: FieldType) -> str:
    if ftype == FieldType.NUMBER:
        return "REAL"
    # DATE stored as ISO TEXT for lexical sort & portability
    return "TEXT"


def _introspect_tables(conn: sqlite3.Connection) -> Dict[str, Dict[str, str]]:
    """Return mapping table_name -> {column_name: declared_type}."""
    cur = conn.cursor()
    cur.execute("SELECT name FROM sqlite_master WHERE type='table'")
    tables = [r[0] for r in cur.fetchall()]
    meta: Dict[str, Dict[str, str]] = {}
    for t in tables:
        cur.execute(f"PRAGMA table_info({t})")
        cols: Dict[str, str] = {}
        for cid, name, coltype, notnull, dflt, pk in cur.fetchall():
            cols[name] = (coltype or "").upper()
        meta[t] = cols
    return meta


def generate_migration_preview(rule_set: RuleSet, conn: sqlite3.Connection) -> MigrationPreview:
    """Generate migration actions comparing live DB to rule-driven schema.

    Parameters
    ----------
    rule_set : RuleSet
        The active rule set.
    conn : sqlite3.Connection
        Connection to current live database (read-only usage expected).
    """
    entries = build_mapping_entries(rule_set)
    grouped = group_by_resource(entries)
    live = _introspect_tables(conn)
    actions: List[MigrationAction] = []

    for resource in sorted(grouped.keys()):
        table_name = resource  # production tables assumed to match resource name
        res_entries = grouped[resource]
        if table_name not in live:
            # Need a CREATE TABLE – build full SQL
            col_defs = []
            for e in res_entries:
                col_defs.append(f"{e.target_column} {_sqlite_type(e.inferred_type)}")
            create_sql = f"CREATE TABLE {table_name} ({', '.join(col_defs)});"
            actions.append(
                MigrationAction(
                    kind="create_table",
                    table=table_name,
                    sql=create_sql,
                    note=f"New table for resource '{resource}'",
                )
            )
            continue
        # Table exists: diff columns
        live_cols = live[table_name]
        for e in res_entries:
            tgt = e.target_column
            expected_type = _sqlite_type(e.inferred_type)
            if tgt not in live_cols:
                actions.append(
                    MigrationAction(
                        kind="add_column",
                        table=table_name,
                        column=tgt,
                        sqlite_type=expected_type,
                        sql=f"ALTER TABLE {table_name} ADD COLUMN {tgt} {expected_type};",
                    )
                )
            else:
                live_type = live_cols[tgt] or ""
                if live_type != expected_type:
                    actions.append(
                        MigrationAction(
                            kind="type_note",
                            table=table_name,
                            column=tgt,
                            sqlite_type=expected_type,
                            note=f"Column '{tgt}' type mismatch (live={live_type or 'UNKNOWN'}, expected={expected_type}); manual migration required.",
                        )
                    )
    return MigrationPreview(actions=actions)
