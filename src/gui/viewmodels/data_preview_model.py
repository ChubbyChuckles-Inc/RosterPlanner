"""Lazy data preview model for the Database panel (Milestone 7.11.3).

The Database panel needs a lightweight, cancellable way to peek at table
rows without loading entire datasets into memory. This module provides a
threaded view-model wrapper around a SQLite connection that issues
paginated ``SELECT`` statements with ``LIMIT``/``OFFSET`` semantics.

Key properties:
    * Requests validate table/column names against the schema introspection
      cache when available (guards against SQL injection vectors).
    * Only one request is executed at a time; issuing a new request
      cancels the previous one via ``sqlite3.Connection.interrupt`` and a
      progress handler hook.
    * Results return column metadata, raw row tuples, and paging details
      so views can bind grids directly.

The model is intentionally GUI-agnostic. Qt views can observe the
``concurrent.futures.Future`` returned from :meth:`fetch_page_async` or
wrap the synchronous :meth:`fetch_page` helper in their own threading
strategy when integrating with Qt signals.
"""

from __future__ import annotations

import re
import sqlite3
import time
from concurrent.futures import Future, ThreadPoolExecutor
from dataclasses import dataclass, field
from threading import Event, RLock
from typing import Iterable, List, Optional, Sequence, Tuple

from gui.services.schema_introspection_service import (
    SchemaIntrospectionService,
    TableInfo,
)

__all__ = [
    "OrderClause",
    "DataPreviewRequest",
    "DataPreviewPage",
    "PreviewCancelledError",
    "LazyDataPreviewModel",
]

# SQLite ``ProgressHandler`` returns non-zero to cancel the current query.
_PROGRESS_STEP = 500
_IDENTIFIER_RE = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*$")


@dataclass(frozen=True)
class OrderClause:
    """Represents a single ORDER BY directive."""

    column: str
    descending: bool = False


@dataclass(frozen=True)
class DataPreviewRequest:
    """Parameters describing a single page fetch."""

    table: str
    offset: int = 0
    limit: int = 100
    ordering: Tuple[OrderClause, ...] = field(default_factory=tuple)
    where: str | None = None
    parameters: Sequence[object] = field(default_factory=tuple)


@dataclass(frozen=True)
class DataPreviewPage:
    """Result payload returned for a preview request."""

    columns: Tuple[str, ...]
    rows: Tuple[Tuple[object, ...], ...]
    offset: int
    limit: int
    total_rows: Optional[int]
    duration_ms: float
    truncated: bool


class PreviewCancelledError(RuntimeError):
    """Raised when an in-flight preview request is cancelled."""


@dataclass
class _PreviewJob:
    request: DataPreviewRequest
    cancel_event: Event
    future: Future[DataPreviewPage]


class LazyDataPreviewModel:
    """Execute paginated SELECT queries with cancellation support."""

    def __init__(
        self,
        conn: sqlite3.Connection | None,
        *,
        introspection: SchemaIntrospectionService | None = None,
        default_limit: int = 100,
        executor_factory: type[ThreadPoolExecutor] = ThreadPoolExecutor,
    ) -> None:
        self._conn = conn
        self._introspection = introspection
        self._default_limit = max(1, default_limit)
        self._executor = executor_factory(max_workers=1, thread_name_prefix="data-preview")
        self._lock = RLock()
        self._active: _PreviewJob | None = None

    # ------------------------------------------------------------------
    # Public API
    def fetch_page_async(self, request: DataPreviewRequest) -> Future[DataPreviewPage]:
        """Schedule a preview request on the worker executor.

        The returned :class:`Future` resolves with a :class:`DataPreviewPage`
        or raises :class:`PreviewCancelledError` if the request is
        cancelled before completion.
        """

        normalized = self._normalize_request(request)
        self._validate_request(normalized)
        with self._lock:
            self._cancel_active_locked()
            if self._conn is None:
                raise RuntimeError("SQLite connection not configured")
            cancel_event = Event()
            job = _PreviewJob(
                request=normalized,
                cancel_event=cancel_event,
                future=self._executor.submit(self._execute_request, normalized, cancel_event),
            )
            self._active = job
            job.future.add_done_callback(lambda _: self._on_job_done(job))
            return job.future

    def fetch_page(
        self, request: DataPreviewRequest, timeout: Optional[float] = None
    ) -> DataPreviewPage:
        """Convenience wrapper returning the result synchronously."""

        future = self.fetch_page_async(request)
        return future.result(timeout=timeout)

    def cancel_active(self) -> None:
        """Cancel the currently running request (if any)."""

        with self._lock:
            self._cancel_active_locked()

    def shutdown(self) -> None:
        """Shutdown the worker executor and cancel active work."""

        with self._lock:
            self._cancel_active_locked()
            try:
                self._executor.shutdown(wait=False, cancel_futures=True)
            except TypeError:  # Python < 3.9 compatibility
                self._executor.shutdown(wait=False)

    # ------------------------------------------------------------------
    # Internal helpers
    def _cancel_active_locked(self) -> None:
        if self._active is None:
            return
        job = self._active
        job.cancel_event.set()
        if self._conn is not None:
            try:
                self._conn.interrupt()
            except Exception:  # pragma: no cover - defensive
                pass
        job.future.cancel()
        self._active = None

    def _normalize_request(self, request: DataPreviewRequest) -> DataPreviewRequest:
        limit = request.limit if request.limit > 0 else self._default_limit
        offset = max(0, request.offset)
        ordering = request.ordering
        return DataPreviewRequest(
            table=request.table.strip(),
            offset=offset,
            limit=limit,
            ordering=ordering,
            where=request.where,
            parameters=tuple(request.parameters),
        )

    def _validate_request(self, request: DataPreviewRequest) -> None:
        if not request.table:
            raise ValueError("Table name required")
        if self._introspection is not None:
            table_info = self._introspection.get_table_info(request.table)
            if table_info is None:
                raise ValueError(f"Unknown table '{request.table}'")
            self._validate_ordering_against_table(request.ordering, table_info)
        else:
            self._validate_identifiers(request.table, [order.column for order in request.ordering])

    def _validate_ordering_against_table(
        self, ordering: Iterable[OrderClause], table: TableInfo
    ) -> None:
        valid_columns = {col.name for col in table.columns}
        for clause in ordering:
            if clause.column not in valid_columns:
                raise ValueError(
                    f"Invalid ORDER BY column '{clause.column}' for table '{table.name}'"
                )

    @staticmethod
    def _validate_identifiers(table: str, columns: Iterable[str]) -> None:
        if not _IDENTIFIER_RE.match(table):
            raise ValueError(f"Invalid table identifier '{table}'")
        for column in columns:
            if not _IDENTIFIER_RE.match(column):
                raise ValueError(f"Invalid column identifier '{column}'")

    def _execute_request(self, request: DataPreviewRequest, cancel_event: Event) -> DataPreviewPage:
        if self._conn is None:
            raise RuntimeError("SQLite connection not configured")
        duration_ms = 0.0
        start = time.perf_counter()
        try:
            self._conn.set_progress_handler(  # type: ignore[attr-defined]
                lambda: 1 if cancel_event.is_set() else 0,
                _PROGRESS_STEP,
            )
            query, params = self._build_query(request)
            cursor = self._conn.execute(query, params)
            rows = cursor.fetchmany(request.limit)
            columns = tuple(desc[0] for desc in cursor.description or [])
        except sqlite3.OperationalError as exc:
            message = str(exc).lower()
            if "interrupt" in message or "cancel" in message:
                raise PreviewCancelledError("Preview query cancelled") from None
            raise
        finally:
            self._conn.set_progress_handler(None, 0)  # type: ignore[attr-defined]
            duration_ms = (time.perf_counter() - start) * 1000.0

        total_rows = self._resolve_total_rows(request.table)
        truncated = self._is_truncated(total_rows, request.offset, len(rows), request.limit)
        return DataPreviewPage(
            columns=columns,
            rows=tuple(tuple(row) for row in rows),
            offset=request.offset,
            limit=request.limit,
            total_rows=total_rows,
            duration_ms=duration_ms,
            truncated=truncated,
        )

    def _build_query(self, request: DataPreviewRequest) -> Tuple[str, Tuple[object, ...]]:
        table_sql = self._quote_ident(request.table)
        sql_parts = [f"SELECT * FROM {table_sql}"]
        params: List[object] = list(request.parameters)
        if request.where:
            sql_parts.append(f"WHERE {request.where}")
        if request.ordering:
            order_sql = ", ".join(
                f"{self._quote_ident(order.column)} {'DESC' if order.descending else 'ASC'}"
                for order in request.ordering
            )
            sql_parts.append(f"ORDER BY {order_sql}")
        sql_parts.append("LIMIT ? OFFSET ?")
        params.extend([request.limit, request.offset])
        return " ".join(sql_parts), tuple(params)

    @staticmethod
    def _quote_ident(value: str) -> str:
        escaped = value.replace('"', '""')
        return f'"{escaped}"'

    def _resolve_total_rows(self, table: str) -> Optional[int]:
        if self._introspection is not None:
            info = self._introspection.get_table_info(table)
            if info is not None:
                return info.row_count
        return None

    @staticmethod
    def _is_truncated(total_rows: Optional[int], offset: int, fetched: int, limit: int) -> bool:
        if total_rows is None:
            return fetched == limit
        return offset + fetched < total_rows

    def _on_job_done(self, job: _PreviewJob) -> None:
        with self._lock:
            if self._active is job:
                self._active = None
