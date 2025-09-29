"""Tests for column statistics sampling in :mod:`schema_introspection_service`."""

from __future__ import annotations

import sqlite3
from typing import List, Optional, Tuple

import pytest

from gui.services.schema_introspection_service import ColumnStats, SchemaIntrospectionService


def _setup_sample_db() -> sqlite3.Connection:
    """Create an in-memory database populated with predictable sample rows."""

    conn = sqlite3.connect(":memory:")
    conn.execute(
        """
        CREATE TABLE matches (
            match_id INTEGER PRIMARY KEY,
            score INTEGER,
            notes TEXT,
            event_date DATE
        )
        """
    )
    rows: List[Tuple[int, Optional[int], Optional[str], Optional[str]]] = [
        (1, 16, "Alpha", "2025-10-02"),
        (2, 12, "Beta", "2025-10-01"),
        (3, None, "Gamma", None),
        (4, 3, None, "2025-09-29"),
    ]
    conn.executemany("INSERT INTO matches VALUES (?, ?, ?, ?)", rows)
    conn.commit()
    return conn


def test_column_stats_sampling_returns_expected_metrics() -> None:
    """Column stats sampler should compute key metrics for each column."""

    conn = _setup_sample_db()
    try:
        service = SchemaIntrospectionService(conn, sample_limit=10)
        stats = service.get_column_stats("matches")
        assert set(stats.keys()) == {"match_id", "score", "notes", "event_date"}

        score_stats: ColumnStats = stats["score"]
        assert score_stats.sample_rows == 4
        assert score_stats.distinct_count == 3
        assert score_stats.null_fraction == pytest.approx(25.0)
        assert score_stats.min_value == "3"
        assert score_stats.max_value == "16"

        notes_stats: ColumnStats = stats["notes"]
        assert notes_stats.sample_rows == 4
        assert notes_stats.distinct_count == 3
        assert notes_stats.null_fraction == pytest.approx(25.0)
        assert notes_stats.min_value is None
        assert notes_stats.max_value is None

        date_stats: ColumnStats = stats["event_date"]
        assert date_stats.sample_rows == 4
        assert date_stats.distinct_count == 3
        assert date_stats.null_fraction == pytest.approx(25.0)
        assert date_stats.min_value == "2025-09-29"
        assert date_stats.max_value == "2025-10-02"

        pk_stats: ColumnStats = stats["match_id"]
        assert pk_stats.sample_rows == 4
        assert pk_stats.distinct_count == 4
        assert pk_stats.null_fraction == pytest.approx(0.0)
        assert pk_stats.min_value == "1"
        assert pk_stats.max_value == "4"
    finally:
        conn.close()


def test_column_stats_cache_respects_max_age() -> None:
    """Sampler should reuse cached statistics until the configured expiry."""

    conn = _setup_sample_db()
    trace: List[str] = []
    conn.set_trace_callback(trace.append)
    try:
        service = SchemaIntrospectionService(conn, sample_limit=10)

        stats_first = service.get_column_stats("matches")
        sample_queries_first = [stmt for stmt in trace if "sample_rows" in stmt]
        assert len(sample_queries_first) == len(stats_first)

        trace.clear()
        service.get_column_stats("matches")
        sample_queries_second = [stmt for stmt in trace if "sample_rows" in stmt]
        assert sample_queries_second == []

        trace.clear()
        service.get_column_stats("matches", max_age_s=-1.0)
        sample_queries_third = [stmt for stmt in trace if "sample_rows" in stmt]
        assert len(sample_queries_third) == len(stats_first)
    finally:
        conn.set_trace_callback(None)
        conn.close()
