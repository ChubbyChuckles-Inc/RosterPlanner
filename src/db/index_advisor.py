"""Index Advisor (Milestone 3.10)

Provides lightweight heuristics to suggest CREATE INDEX statements for SELECT
queries that perform full table scans according to ``EXPLAIN QUERY PLAN`` and
include simple equality predicates in their WHERE clause.

Scope (intentionally constrained for milestone):
 - Detect full scans reported as 'SCAN TABLE <name>' or 'SEARCH TABLE <name> USING INTEGER PRIMARY KEY' (skip PK search).
 - Parse WHERE clause for patterns: ``col = ?`` or ``col = <literal>`` joined by AND.
 - Skip columns that already have an index (using PRAGMA index_list / index_info) or are the primary key.
 - Provide composite index suggestion if multiple equality predicates on the same table.

Future enhancements could include range predicate handling, selectivity estimates,
join analysis, and multi-table queries.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import List, Sequence, Dict, Tuple
import sqlite3
import re

__all__ = [
    "IndexSuggestion",
    "analyze_query_for_indexes",
    "advise_indexes",
]

_WHERE_EQ_RE = re.compile(r"\b([A-Za-z_][A-Za-z0-9_]*)\s*=\s*(?:\?|[0-9]+|'[^']*')")


@dataclass
class IndexSuggestion:
    table: str
    columns: Tuple[str, ...]
    reason: str
    create_sql: str

    def composite_key(self) -> str:
        return ",".join(self.columns)


def _existing_indexes(conn: sqlite3.Connection, table: str) -> List[Tuple[str, Tuple[str, ...]]]:
    cur = conn.execute(f"PRAGMA index_list('{table}')")
    out: List[Tuple[str, Tuple[str, ...]]] = []
    for row in cur.fetchall():  # seq, name, unique, origin, partial
        idx_name = row[1]
        cols_cur = conn.execute(f"PRAGMA index_info('{idx_name}')")
        cols = tuple(r[2] for r in cols_cur.fetchall())
        out.append((idx_name, cols))
    return out


def _table_pk_columns(conn: sqlite3.Connection, table: str) -> List[str]:
    pk_cols: List[str] = []
    cur = conn.execute(f"PRAGMA table_info('{table}')")
    for cid, name, type_, notnull, dflt, pk in cur.fetchall():  # noqa: F841
        if pk:
            pk_cols.append(name)
    return pk_cols


def analyze_query_for_indexes(conn: sqlite3.Connection, sql: str) -> List[IndexSuggestion]:
    # Simplify detection: only handle single-table SELECT statements.
    lowered = sql.strip().lower()
    if not lowered.startswith("select"):
        return []
    # Acquire query plan
    plan_rows = conn.execute(f"EXPLAIN QUERY PLAN {sql}").fetchall()
    suggestions: List[IndexSuggestion] = []
    # Parse WHERE clause (very naive split on ' where ')
    where_part = ""
    idx = lowered.find(" where ")
    if idx != -1:
        # Slice original SQL from matching offset (keeps original column case)
        where_part = sql[idx + len(" where ") :]
    # Collect equality columns per table (preserve order, dedupe)
    seen_cols: set[str] = set()
    eq_cols: list[str] = []
    for m in _WHERE_EQ_RE.finditer(where_part):
        col = m.group(1)
        if col not in seen_cols:
            seen_cols.add(col)
            eq_cols.append(col)
    # We'll only attempt if there is at least one equality.
    if not eq_cols:
        return []
    # For each plan row determine table and scan type
    for _, _, _, detail in plan_rows:
        # detail examples: 'SCAN t', 'SEARCH t USING INTEGER PRIMARY KEY', 'SEARCH t USING INDEX idx_x'
        d_low = detail.lower()
        if " using " in d_low and "primary key" in d_low:
            continue  # PK already leveraged
        if " using index " in d_low:
            continue  # Already using an index
        if "scan" not in d_low and "search" not in d_low:
            continue
        # Extract table name (naive: word after scan/search)
        tokens = d_low.split()
        table = None
        for i, tok in enumerate(tokens):
            if tok in ("scan", "search") and i + 1 < len(tokens):
                table = tokens[i + 1]
                break
        if not table:
            continue
        pk_cols = set(_table_pk_columns(conn, table))
        existing = _existing_indexes(conn, table)
        existing_sets = {cols for _, cols in existing}
        # Filter eq columns that belong to this table (assume unqualified)
        table_eq_cols = [c for c in eq_cols if c not in pk_cols]
        if not table_eq_cols:
            continue
        # If multiple equality columns, propose composite first if not already existing.
        if len(table_eq_cols) > 1:
            composite = tuple(table_eq_cols)
            if composite not in existing_sets:
                create_sql = f"CREATE INDEX idx_{table}_{'_'.join(table_eq_cols)} ON {table}({', '.join(table_eq_cols)});"
                suggestions.append(
                    IndexSuggestion(
                        table=table,
                        columns=composite,
                        reason="Multiple equality predicates - composite index",
                        create_sql=create_sql,
                    )
                )
                continue  # don't suggest individual columns after composite for now
        # Otherwise suggest individual indexes for columns lacking one
        for col in table_eq_cols:
            if any(col in cols for cols in existing_sets):
                continue
            create_sql = f"CREATE INDEX idx_{table}_{col} ON {table}({col});"
            suggestions.append(
                IndexSuggestion(
                    table=table,
                    columns=(col,),
                    reason="Equality predicate no supporting index",
                    create_sql=create_sql,
                )
            )
    return suggestions


def advise_indexes(conn: sqlite3.Connection, queries: Sequence[str]) -> List[IndexSuggestion]:
    out: List[IndexSuggestion] = []
    seen: set[tuple[str, Tuple[str, ...]]] = set()
    for q in queries:
        for s in analyze_query_for_indexes(conn, q):
            key = (s.table, s.columns)
            if key not in seen:
                out.append(s)
                seen.add(key)
    return out
