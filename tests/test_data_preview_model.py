"""Unit tests for the lazy data preview model (Milestone 7.11.3)."""

from __future__ import annotations

import sqlite3
import threading
import time

import pytest

from gui.services.schema_introspection_service import SchemaIntrospectionService
from gui.viewmodels.data_preview_model import (
    DataPreviewRequest,
    LazyDataPreviewModel,
    OrderClause,
    PreviewCancelledError,
)


def _create_connection() -> sqlite3.Connection:
    conn = sqlite3.connect(":memory:", check_same_thread=False)
    conn.execute("PRAGMA foreign_keys=ON")
    return conn


def test_fetch_page_returns_expected_rows() -> None:
    conn = _create_connection()
    try:
        conn.execute("CREATE TABLE demo (id INTEGER PRIMARY KEY, name TEXT)")
        for idx in range(5):
            conn.execute("INSERT INTO demo (name) VALUES (?)", (f"row-{idx}",))
        conn.commit()

        introspection = SchemaIntrospectionService(conn)
        introspection.refresh()

        model = LazyDataPreviewModel(conn, introspection=introspection)
        try:
            request = DataPreviewRequest(
                table="demo",
                limit=2,
                offset=1,
                ordering=(OrderClause("id"),),
            )
            page = model.fetch_page(request, timeout=1.0)
        finally:
            model.shutdown()

        assert page.columns == ("id", "name")
        assert page.rows == ((2, "row-1"), (3, "row-2"))
        assert page.offset == 1
        assert page.limit == 2
        assert page.total_rows == 5
        assert page.truncated is True
        assert page.duration_ms >= 0.0
    finally:
        conn.close()


def test_cancel_active_interrupts_query() -> None:
    conn = _create_connection()
    try:
        conn.execute("CREATE TABLE slow_demo (id INTEGER PRIMARY KEY, value TEXT)")
        for idx in range(50):
            conn.execute("INSERT INTO slow_demo (value) VALUES (?)", (f"value-{idx}",))
        conn.commit()

        start_event = threading.Event()

        def slow(value: str) -> None:
            start_event.set()
            time.sleep(0.01)
            return None

        conn.create_function("slow", 1, slow)

        introspection = SchemaIntrospectionService(conn)
        introspection.refresh()

        model = LazyDataPreviewModel(conn, introspection=introspection)
        try:
            request = DataPreviewRequest(
                table="slow_demo",
                limit=50,
                ordering=(OrderClause("id"),),
                where="slow(value) IS NULL OR 1=1",
            )
            future = model.fetch_page_async(request)
            assert start_event.wait(1.0)
            model.cancel_active()
            with pytest.raises(PreviewCancelledError):
                future.result(timeout=2.0)
        finally:
            model.shutdown()
    finally:
        conn.close()


def test_invalid_ordering_column_raises() -> None:
    conn = _create_connection()
    try:
        conn.execute("CREATE TABLE demo (id INTEGER PRIMARY KEY, name TEXT)")
        conn.commit()
        introspection = SchemaIntrospectionService(conn)
        introspection.refresh()

        model = LazyDataPreviewModel(conn, introspection=introspection)
        try:
            with pytest.raises(ValueError):
                model.fetch_page_async(
                    DataPreviewRequest(table="demo", ordering=(OrderClause("missing"),))
                )
        finally:
            model.shutdown()
    finally:
        conn.close()
