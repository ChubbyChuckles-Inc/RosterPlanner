from __future__ import annotations

import sqlite3

from gui.services.schema_introspection_service import SchemaIntrospectionService
from gui.services.foreign_key_orphan_detector import ForeignKeyOrphanDetector


def _build_connection_with_orphans() -> sqlite3.Connection:
    conn = sqlite3.connect(":memory:")
    conn.execute("PRAGMA foreign_keys=OFF")
    conn.execute("CREATE TABLE parent(id INTEGER PRIMARY KEY, name TEXT)")
    conn.execute(
        "CREATE TABLE child(id INTEGER PRIMARY KEY, parent_id INTEGER, "
        "FOREIGN KEY(parent_id) REFERENCES parent(id))"
    )
    conn.execute("INSERT INTO parent(id, name) VALUES (1, 'kept')")
    conn.executemany(
        "INSERT INTO child(id, parent_id) VALUES (?, ?)",
        [
            (1, 1),
            (2, 1),
            (3, 99),  # orphan
            (4, None),
        ],
    )
    conn.execute("PRAGMA foreign_keys=ON")
    conn.commit()
    return conn


def _build_connection_with_composite_orphan() -> sqlite3.Connection:
    conn = sqlite3.connect(":memory:")
    conn.execute("PRAGMA foreign_keys=OFF")
    conn.execute("CREATE TABLE parent(a INTEGER, b INTEGER, PRIMARY KEY(a, b))")
    conn.execute(
        "CREATE TABLE child(id INTEGER PRIMARY KEY, a INTEGER, b INTEGER, "
        "FOREIGN KEY(a, b) REFERENCES parent(a, b))"
    )
    conn.executemany("INSERT INTO parent(a, b) VALUES (?, ?)", [(1, 1), (2, 2)])
    conn.executemany(
        "INSERT INTO child(id, a, b) VALUES (?, ?, ?)",
        [
            (1, 1, 1),
            (2, 2, 2),
            (3, 1, 2),  # orphan combination
        ],
    )
    conn.execute("PRAGMA foreign_keys=ON")
    conn.commit()
    return conn


def test_orphan_detector_reports_single_column_fk() -> None:
    conn = _build_connection_with_orphans()
    try:
        schema = SchemaIntrospectionService(conn)
        detector = ForeignKeyOrphanDetector(conn, schema)
        report = detector.scan()
        assert report.findings
        finding = report.findings[0]
        assert finding.table == "child"
        assert finding.columns == ("parent_id",)
        assert finding.ref_table == "parent"
        assert finding.orphan_count == 1
        assert any("parent_id=99" in sample for sample in finding.sample_rows)
        formatted = detector.format_report(report)
        assert "child(parent_id) -> parent(id)" in formatted
    finally:
        conn.close()


def test_orphan_detector_supports_composite_foreign_keys() -> None:
    conn = _build_connection_with_composite_orphan()
    try:
        schema = SchemaIntrospectionService(conn)
        detector = ForeignKeyOrphanDetector(conn, schema)
        report = detector.scan()
        assert report.total_orphans() == 1
        finding = report.findings[0]
        assert finding.columns == ("a", "b")
        assert finding.ref_columns == ("a", "b")
        assert any("a=1" in sample and "b=2" in sample for sample in finding.sample_rows)
    finally:
        conn.close()
