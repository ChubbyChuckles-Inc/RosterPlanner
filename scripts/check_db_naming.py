"""Check DB naming conventions (Milestone 3.1.2)

Usage:
    python -m scripts.check_db_naming

Exits with code 0 if all naming conventions pass, else 1.
"""

from __future__ import annotations
import sys
import sqlite3
from db import apply_schema
from db.naming import validate_naming_conventions


def main() -> int:
    conn = sqlite3.connect(":memory:")
    conn.execute("PRAGMA foreign_keys=ON")
    apply_schema(conn)
    violations = validate_naming_conventions(conn)
    if violations:
        for v in violations:
            print(f"NAMING VIOLATION: {v}")
        return 1
    print("All naming conventions passed.")
    return 0


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
