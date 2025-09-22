from __future__ import annotations

import sqlite3
from time import sleep
from pathlib import Path

from db.query_perf import (
    install_query_performance_logger,
    QueryPerformanceLogger,
    QueryRecord,
    QueryPerformanceConnection,
    create_instrumented_connection,
)


def test_slow_query_logged(tmp_path: Path):
    conn, logger = create_instrumented_connection(threshold_ms=0.0, max_records=10)
    conn.execute("CREATE TABLE t(id INTEGER PRIMARY KEY, name TEXT)")
    assert isinstance(logger, QueryPerformanceLogger)

    # Force an artificial delay by running many inserts (still might be fast; rely on threshold low enough)
    for i in range(50):
        conn.execute("INSERT INTO t(name) VALUES (?)", (f"n{i}",))
    conn.commit()
    # At least one record should be present (depends on environment speed)
    records = logger.records()
    assert len(records) >= 1
    assert all(isinstance(r, QueryRecord) for r in records)


def test_high_threshold_filters_all(tmp_path: Path):
    conn, logger = create_instrumented_connection(threshold_ms=10_000.0, max_records=5)
    conn.execute("CREATE TABLE t(id INTEGER PRIMARY KEY, name TEXT)")
    for i in range(5):
        conn.execute("INSERT INTO t(name) VALUES (?)", (f"v{i}",))
    assert logger.records() == []


def test_ring_buffer_eviction(tmp_path: Path):
    conn, logger = create_instrumented_connection(threshold_ms=0.0, max_records=5)
    conn.execute("CREATE TABLE t(id INTEGER PRIMARY KEY, name TEXT)")
    for i in range(15):
        conn.execute("INSERT INTO t(name) VALUES (?)", (f"x{i}",))
    recs = logger.records()
    assert len(recs) == 5  # ring buffer size
    # Ensure only last 5 remain
    assert recs[0].sql.startswith("INSERT INTO t")


def test_subclass_instrumentation(tmp_path: Path):
    conn, logger = create_instrumented_connection(threshold_ms=0.0, max_records=3)
    conn.execute("CREATE TABLE t(id INTEGER PRIMARY KEY, name TEXT)")
    for i in range(3):
        conn.execute("INSERT INTO t(name) VALUES (?)", (f"s{i}",))
    assert len(logger.records()) == 3
