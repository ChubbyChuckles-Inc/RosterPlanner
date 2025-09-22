"""Query Performance Logging (Milestone 3.9)

Provides a lightweight instrumentation layer for sqlite3 connections to record
slow queries whose wall time exceeds a configurable threshold. Designed to be
low-overhead and opt-in.

Approach:
 - Wrap cursor execute / executemany and measure elapsed time with perf_counter.
 - If >= threshold_ms, append record to an in-memory ring buffer plus (optional)
   emit to logging.
 - Provide API to install instrumentation per connection and retrieve stats.
 - Expose a dataclass for structured records for future UI surfacing.

We keep implementation dependency-free and avoid global monkey patching.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Callable, List, Optional, Any, Deque
from time import perf_counter
from collections import deque
import sqlite3

try:  # optional logging
    import logging

    _log = logging.getLogger(__name__)
except Exception:  # pragma: no cover

    class _Dummy:
        def debug(self, *a, **k):
            pass

        def info(self, *a, **k):
            pass

        def warning(self, *a, **k):
            pass

        def error(self, *a, **k):
            pass

    _log = _Dummy()

__all__ = [
    "QueryRecord",
    "QueryPerformanceLogger",
    "install_query_performance_logger",
    "create_instrumented_connection",
    "QueryPerformanceConnection",
]


@dataclass
class QueryRecord:
    sql: str
    params: Any
    ms: float
    rowcount: int | None


class QueryPerformanceLogger:
    """Holds slow query records in a bounded ring buffer."""

    def __init__(self, max_records: int = 200):
        self._records: Deque[QueryRecord] = deque(maxlen=max_records)

    def add(self, rec: QueryRecord):
        self._records.append(rec)

    def records(self) -> List[QueryRecord]:  # copy for safety
        return list(self._records)

    def clear(self):
        self._records.clear()


class _InstrumentedCursor(sqlite3.Cursor):  # pragma: no cover - thin wrapper exercised indirectly
    def __init__(self, *a, **k):  # type: ignore[override]
        super().__init__(*a, **k)
        self._qpl: QueryPerformanceLogger | None = None
        self._threshold_ms: float = 0.0
        self._log_enabled: bool = False

    def configure(self, logger: QueryPerformanceLogger, threshold_ms: float, log_enabled: bool):
        self._qpl = logger
        self._threshold_ms = threshold_ms
        self._log_enabled = log_enabled

    def execute(self, sql, parameters=()):  # type: ignore[override]
        start = perf_counter()
        try:
            return super().execute(sql, parameters)
        finally:
            self._after(sql, parameters, start)

    def executemany(self, sql, seq_of_parameters):  # type: ignore[override]
        start = perf_counter()
        try:
            return super().executemany(sql, seq_of_parameters)
        finally:
            self._after(sql, seq_of_parameters, start)

    def _after(self, sql, params, start):
        if not self._qpl:
            return
        elapsed_ms = (perf_counter() - start) * 1000.0
        if elapsed_ms >= self._threshold_ms:
            rc = None
            try:
                rc = self.rowcount  # type: ignore[attr-defined]
            except Exception:
                rc = None
            rec = QueryRecord(sql=sql, params=params, ms=elapsed_ms, rowcount=rc)
            self._qpl.add(rec)
            if self._log_enabled:
                _log.info("slow query %.2f ms: %s", elapsed_ms, sql)


class QueryPerformanceConnection(
    sqlite3.Connection
):  # pragma: no cover - creation tested indirectly
    def __init__(self, *a, **k):  # type: ignore[override]
        super().__init__(*a, **k)
        self._qpl_logger: QueryPerformanceLogger | None = None
        self._qpl_threshold_ms: float = 0.0
        self._qpl_log_enabled: bool = False

    def cursor(self, *a, **k):  # type: ignore[override]
        cur = super().cursor(factory=_InstrumentedCursor)
        if self._qpl_logger:
            cur.configure(self._qpl_logger, self._qpl_threshold_ms, self._qpl_log_enabled)
        return cur

    # Ensure execute/go through instrumented cursor
    def execute(self, *a, **k):  # type: ignore[override]
        cur = self.cursor()
        return cur.execute(*a, **k)

    def executemany(self, *a, **k):  # type: ignore[override]
        cur = self.cursor()
        return cur.executemany(*a, **k)

    # Public helpers
    def set_query_performance_logger(
        self, logger: QueryPerformanceLogger, threshold_ms: float, log_enabled: bool
    ):
        self._qpl_logger = logger
        self._qpl_threshold_ms = threshold_ms
        self._qpl_log_enabled = log_enabled

    def get_query_performance_logger(self) -> QueryPerformanceLogger | None:
        return self._qpl_logger


# Installation API -------------------------------------------------


def install_query_performance_logger(
    conn: sqlite3.Connection,
    threshold_ms: float = 25.0,
    max_records: int = 200,
    log_enabled: bool = False,
) -> QueryPerformanceLogger:
    """Install slow query instrumentation.

    Only supported for :class:`QueryPerformanceConnection` instances. Raises
    ValueError for plain sqlite3 connections to encourage explicit factory use.
    """
    if not isinstance(conn, QueryPerformanceConnection):  # pragma: no cover - defensive
        raise ValueError("Connection must be created with factory=QueryPerformanceConnection")
    logger = conn.get_query_performance_logger() or QueryPerformanceLogger(max_records=max_records)
    conn.set_query_performance_logger(logger, threshold_ms, log_enabled)
    return logger


def create_instrumented_connection(
    path: str | None = None,
    *,
    threshold_ms: float = 25.0,
    max_records: int = 200,
    log_enabled: bool = False,
    **connect_kwargs,
) -> tuple[sqlite3.Connection, QueryPerformanceLogger]:
    """Factory returning an instrumented connection and its logger.

    Args:
        path: File path or None for in-memory.
        threshold_ms: Slow query threshold.
        max_records: Ring buffer size.
        log_enabled: Emit log lines when capturing slow queries.
        connect_kwargs: Extra keyword args forwarded to ``sqlite3.connect``.
    """
    target = path or ":memory:"
    conn = sqlite3.connect(target, factory=QueryPerformanceConnection, **connect_kwargs)
    logger = install_query_performance_logger(
        conn, threshold_ms=threshold_ms, max_records=max_records, log_enabled=log_enabled
    )
    return conn, logger
