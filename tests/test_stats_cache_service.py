"""Tests for StatsCacheService (Milestone 6.7)."""

from __future__ import annotations

import sqlite3
import time
import pytest
from datetime import datetime, timedelta

from src.gui.services.stats_cache_service import StatsCacheService
from src.gui.services.service_locator import services
from src.gui.services.data_freshness_service import DataFreshnessService


@pytest.fixture(autouse=True)
def sqlite_conn(tmp_path):
    # Minimal DB with provenance_summary to simulate ingest timestamp changes
    conn = sqlite3.connect(":memory:")
    conn.row_factory = sqlite3.Row
    conn.executescript(
        """
        CREATE TABLE provenance_summary (ingested_at TEXT);
        INSERT INTO provenance_summary (ingested_at) VALUES ('2025-01-01T00:00:00');
        """
    )
    services.register("sqlite_conn", conn)
    yield conn
    services.unregister("sqlite_conn")
    conn.close()


def test_cache_basic_get_or_compute():
    cache = StatsCacheService()
    calls = {"count": 0}

    def compute():
        calls["count"] += 1
        return 42

    v1 = cache.get_or_compute("kpi.test", {"team": "t1"}, compute)
    v2 = cache.get_or_compute("kpi.test", {"team": "t1"}, compute)
    assert v1 == 42 and v2 == 42
    assert calls["count"] == 1  # second call cached


def test_cache_invalidation_on_new_ingest(sqlite_conn):
    cache = StatsCacheService()
    calls = {"count": 0}

    def compute():
        calls["count"] += 1
        return 99

    first = cache.get_or_compute("kpi.test", {"team": "t1"}, compute)
    assert first == 99 and calls["count"] == 1
    # Simulate new ingest by inserting newer timestamp
    sqlite_conn.execute(
        "INSERT INTO provenance_summary (ingested_at) VALUES (?)",
        ("2025-01-02T00:00:00",),
    )
    sqlite_conn.commit()
    second = cache.get_or_compute("kpi.test", {"team": "t1"}, compute)
    # Freshness token changed -> recompute
    assert second == 99 and calls["count"] == 2


def test_manual_prefix_invalidation():
    cache = StatsCacheService()
    cache.get_or_compute("kpi.win_pct", {"team": "A"}, lambda: 1.0)
    cache.get_or_compute("kpi.avg_pz", {"team": "A"}, lambda: 2.0)
    cache.get_or_compute("chart.series", {"team": "A"}, lambda: [1, 2])
    removed = cache.invalidate(prefix="kpi.")
    stats = cache.stats()
    assert removed == 2
    assert stats["entries"] == 1  # only chart.series remains


def test_cache_without_freshness():
    cache = StatsCacheService()
    calls = {"count": 0}

    def compute():
        calls["count"] += 1
        return "stable"

    v1 = cache.get_or_compute("stable.metric", {"team": "t1"}, compute, include_freshness=False)
    v2 = cache.get_or_compute("stable.metric", {"team": "t1"}, compute, include_freshness=False)
    assert v1 == v2 == "stable"
    assert calls["count"] == 1
