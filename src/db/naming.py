"""Database Naming Conventions (Milestone 3.1.2)

This module enforces standardized naming conventions for database objects.

Current scope: table names only.

Rules:
- snake_case (lowercase letters, digits, underscores; must start with a letter)
- singular nouns (best-effort heuristic: disallow trailing 's' for now except for explicitly whitelisted cases)
- reserved internal tables (sqlite_sequence, schema_meta) are ignored

Future expansions (planned in later milestones):
- column naming rules
- index naming (idx_<table>_<columns>)
- trigger naming

Public API:
- validate_naming_conventions(conn) -> list[str]: returns list of violation messages.
"""

from __future__ import annotations
import re
import sqlite3
from typing import List

INTERNAL_TABLES = {"sqlite_sequence", "schema_meta"}
ALLOWED_TRAILING_S = {"status"}  # words that legitimately end with s but are singular
TABLE_NAME_RE = re.compile(r"^[a-z][a-z0-9_]*$")


def _is_singular(name: str) -> bool:
    # Naive heuristic: Disallow trailing 's' unless whitelisted, but allow names <3 chars.
    if len(name) < 3:
        return True
    if name in ALLOWED_TRAILING_S:
        return True
    return not name.endswith("s")


def validate_naming_conventions(conn: sqlite3.Connection) -> List[str]:
    cur = conn.cursor()
    cur.execute("SELECT name FROM sqlite_master WHERE type='table'")
    violations: List[str] = []
    for (name,) in cur.fetchall():
        if name in INTERNAL_TABLES:
            continue
        if not TABLE_NAME_RE.match(name):
            violations.append(
                f"Table '{name}' is not snake_case (expected pattern {TABLE_NAME_RE.pattern})"
            )
        if not _is_singular(name):
            violations.append(f"Table '{name}' should be singular (heuristic check failed)")
    return violations


__all__ = ["validate_naming_conventions"]
