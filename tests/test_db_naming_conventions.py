from __future__ import annotations
import sqlite3
from db import apply_schema
from db.naming import validate_naming_conventions


def test_table_naming_conventions_pass_for_current_schema():
    conn = sqlite3.connect(":memory:")
    conn.execute("PRAGMA foreign_keys=ON")
    apply_schema(conn)
    violations = validate_naming_conventions(conn)
    assert violations == [], f"Unexpected naming violations: {violations}"
