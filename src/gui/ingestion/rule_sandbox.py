"""Alternate Target Schema Sandbox (Milestone 7.10.12)

Creates an in-memory (or temporary) SQLite schema derived from the current
``RuleSet`` + mapping inference so users can experiment with transformed data
before committing migrations. Later milestones will populate this with preview
ingest rows and generate diff / migration SQL.

Key Responsibilities (initial scope):
 - Translate mapping entries (list + table resources) into CREATE TABLE DDL.
 - Allow optional per-field type overrides supplied by UI (e.g. user forces
   a field inferred as STRING to NUMBER).
 - Provide an API returning the generated DDL + a convenience function to
   apply it to a fresh in-memory SQLite connection.

Type Mapping:
 FieldType.STRING -> TEXT
 FieldType.NUMBER -> REAL (SQLite dynamic typing; REAL chosen to cover int/float)
 FieldType.DATE   -> TEXT (ISO-8601 date strings kept lexical; later we could
                          add a CHECK constraint or store as INTEGER epoch)
 FieldType.UNKNOWN -> TEXT

Future Extensions (NOT in this milestone):
 - Persist sandbox DB between sessions.
 - Generate migration diff vs live schema.
 - Apply constraints (PRIMARY KEY, UNIQUE) based on heuristics or user input.
 - Track provenance of inserted preview rows.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, List, Mapping, Tuple, Optional
import sqlite3

from .rule_mapping import build_mapping_entries, FieldType, MappingEntry, group_by_resource
from .rule_schema import RuleSet

__all__ = [
    "SandboxTable",
    "SandboxSchema",
    "build_sandbox_schema",
    "apply_sandbox_schema",
]


@dataclass
class SandboxTable:
    name: str
    columns: List[Tuple[str, FieldType]]  # ordered (column_name, field_type)

    def create_sql(self) -> str:
        col_defs = []
        for cname, ftype in self.columns:
            sqlite_type = _sqlite_type(ftype)
            col_defs.append(f"{cname} {sqlite_type}")
        cols_sql = ", ".join(col_defs)
        return f"CREATE TABLE {self.name} ({cols_sql});"


@dataclass
class SandboxSchema:
    tables: List[SandboxTable]

    def ddl(self) -> List[str]:  # convenience
        return [t.create_sql() for t in self.tables]


def _sqlite_type(ftype: FieldType) -> str:
    if ftype == FieldType.NUMBER:
        return "REAL"
    if ftype == FieldType.DATE:
        return "TEXT"
    if ftype == FieldType.UNKNOWN:
        return "TEXT"
    return "TEXT"


TypeOverrideMap = Mapping[Tuple[str, str], FieldType]


def build_sandbox_schema(
    rule_set: RuleSet, overrides: Optional[TypeOverrideMap] = None
) -> SandboxSchema:
    """Build a sandbox schema from a rule set.

    Parameters
    ----------
    rule_set: RuleSet
        Current rule set.
    overrides: Mapping[(resource, source_name) -> FieldType]
        Optional explicit type overrides from the UI.
    """
    entries = build_mapping_entries(rule_set)
    grouped = group_by_resource(entries)
    tables: List[SandboxTable] = []
    for resource, res_entries in grouped.items():
        table_name = f"sandbox_{resource}"
        cols: List[Tuple[str, FieldType]] = []
        for e in res_entries:
            ftype = (
                overrides.get((e.resource, e.source_name), e.inferred_type)
                if overrides
                else e.inferred_type
            )
            cols.append((e.target_column, ftype))
        tables.append(SandboxTable(name=table_name, columns=cols))
    return SandboxSchema(tables=tables)


def apply_sandbox_schema(schema: SandboxSchema) -> sqlite3.Connection:
    """Create an in-memory SQLite connection and apply the schema DDL."""
    conn = sqlite3.connect(":memory:")
    cur = conn.cursor()
    for sql in schema.ddl():
        cur.execute(sql)
    conn.commit()
    return conn
