"""ER Diagram Generation (Milestone 3.1.1)

Generates a Mermaid ER diagram representation of the current SQLite schema.
This is intended to support documentation automation for the schema.

Approach:
- Introspect `sqlite_master` for tables (excluding internal tables like sqlite_sequence).
- For each table, extract columns via PRAGMA table_info.
- Extract foreign key relations via PRAGMA foreign_key_list.
- Render a Mermaid ER diagram using `erDiagram` syntax.

Limitations:
- Does not yet show index metadata or cardinality annotations beyond simple FK.
- Future enhancement: detect associative tables (many-to-many) and mark accordingly.

Usage:
    from db.er import generate_er_mermaid
    diagram = generate_er_mermaid(conn)

Testing:
- See tests/test_er_diagram.py for ensuring all core tables and known relationships appear.
"""

from __future__ import annotations
import sqlite3
from typing import Dict, List, Tuple

INTERNAL_TABLES = {"sqlite_sequence", "schema_meta"}


def _get_tables(conn: sqlite3.Connection) -> List[str]:
    cur = conn.cursor()
    cur.execute("SELECT name FROM sqlite_master WHERE type='table' ORDER BY name")
    return [r[0] for r in cur.fetchall() if r[0] not in INTERNAL_TABLES]


def _get_columns(conn: sqlite3.Connection, table: str) -> List[Tuple[str, str, bool]]:
    cur = conn.cursor()
    cur.execute(f"PRAGMA table_info('{table}')")
    cols: List[Tuple[str, str, bool]] = []
    for cid, name, col_type, notnull, default, pk in cur.fetchall():  # type: ignore
        nullable = not bool(notnull) and not bool(pk)
        # Simplify type for display
        col_type_disp = (col_type or "").upper().split("(")[0]
        cols.append((name, col_type_disp, nullable))
    return cols


def _get_foreign_keys(conn: sqlite3.Connection, table: str) -> List[Tuple[str, str, str]]:
    cur = conn.cursor()
    cur.execute(f"PRAGMA foreign_key_list('{table}')")
    fks = []
    for row in cur.fetchall():  # type: ignore
        # (id, seq, table, from, to, on_update, on_delete, match)
        _id, _seq, ref_table, from_col, to_col, *_rest = row
        fks.append((from_col, ref_table, to_col))
    return fks


def generate_er_mermaid(conn: sqlite3.Connection) -> str:
    """Generate Mermaid ER diagram text for the current schema.

    Returns:
        Mermaid `erDiagram` text block.
    """
    tables = _get_tables(conn)
    table_cols: Dict[str, List[Tuple[str, str, bool]]] = {t: _get_columns(conn, t) for t in tables}
    relationships: List[Tuple[str, str, str, str]] = (
        []
    )  # (left_table, left_col, right_table, right_col)
    for t in tables:
        for from_col, ref_table, to_col in _get_foreign_keys(conn, t):
            relationships.append((t, from_col, ref_table, to_col))

    lines: List[str] = ["erDiagram"]

    # Table definitions
    for table in tables:
        lines.append(f"  {table} {{")
        for name, col_type, nullable in table_cols[table]:
            # Mermaid ER syntax uses format: <type> <name>
            null_suffix = "?" if nullable else ""
            type_disp = col_type or "TEXT"
            lines.append(f"    {type_disp} {name}{null_suffix}")
        lines.append("  }")
        lines.append("")

    # Relationships (basic cardinality inference: assuming many-to-one on FK side)
    for left_table, left_col, right_table, right_col in relationships:
        # left_table N--1 right_table : "left_col -> right_col"
        lines.append(f'  {left_table} }}o--|| {right_table} : "{left_col} -> {right_col}"')

    return "\n".join(lines).strip() + "\n"


__all__ = ["generate_er_mermaid"]
