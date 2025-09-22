"""CLI: Run integrity checks against a SQLite database file.

Usage:
  python -m scripts.check_db_integrity path/to/db.sqlite

Exits with code 0 if clean, 1 if issues found.
"""

from __future__ import annotations

import json
import sqlite3
import sys
from pathlib import Path

from db.integrity import run_integrity_checks


def main(argv: list[str] | None = None) -> int:
    argv = argv or sys.argv[1:]
    if not argv:
        print("Usage: python -m scripts.check_db_integrity <db_path>", file=sys.stderr)
        return 2
    db_path = Path(argv[0])
    if not db_path.exists():
        print(f"Database file not found: {db_path}", file=sys.stderr)
        return 2
    conn = sqlite3.connect(str(db_path))
    conn.execute("PRAGMA foreign_keys=ON")
    try:
        issues = run_integrity_checks(conn)
    finally:
        conn.close()
    if issues:
        print(
            json.dumps({"status": "fail", "issue_count": len(issues), "issues": issues}, indent=2)
        )
        return 1
    print(json.dumps({"status": "ok", "issue_count": 0}, indent=2))
    return 0


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
