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


def _populate_player_table(conn: sqlite3.Connection) -> None:
    conn.execute(
        "CREATE TABLE players (player_id INTEGER PRIMARY KEY, name TEXT, notes TEXT)"
    )
    rows = [
        (1, "Alice", "Captain"),
        (2, "Bob", "Bench"),
        (3, "Alicia", "Starter"),
    ]
    conn.executemany("INSERT INTO players VALUES (?, ?, ?)", rows)
    conn.commit()


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


def test_build_quick_filter_clause_escapes_characters() -> None:
    conn = _create_connection()
    try:
        _populate_player_table(conn)
        introspection = SchemaIntrospectionService(conn)
        introspection.refresh()
        model = LazyDataPreviewModel(conn, introspection=introspection)
        try:
            clause, params = model.build_quick_filter_clause("players", "A%l_ice")
        finally:
            model.shutdown()

        assert clause.startswith("(") and clause.endswith(")")
        assert clause.count("LIKE ?") == len(introspection.get_table_info("players").columns)
        assert params[0] == "%A\\%l\\_ice%"
    finally:
        conn.close()


def test_quick_filter_limits_rows_to_matches() -> None:
    conn = _create_connection()
    try:
        _populate_player_table(conn)
        introspection = SchemaIntrospectionService(conn)
        introspection.refresh()
        model = LazyDataPreviewModel(conn, introspection=introspection)
        try:
            request = DataPreviewRequest(table="players", quick_filter="ali")
            page = model.fetch_page(request)
        finally:
            model.shutdown()

        names = [row[1] for row in page.rows]
        assert names == ["Alice", "Alicia"]
    finally:
        conn.close()


def test_apply_quick_filter_combines_with_existing_where_clause() -> None:
    conn = _create_connection()
    try:
        _populate_player_table(conn)
        introspection = SchemaIntrospectionService(conn)
        introspection.refresh()
        model = LazyDataPreviewModel(conn, introspection=introspection)
        try:
            base_request = DataPreviewRequest(
                table="players",
                where="player_id > ?",
                parameters=(1,),
            )
            filtered_request = model.apply_quick_filter(base_request, "bob")
            page = model.fetch_page(filtered_request)
        finally:
            model.shutdown()

        assert len(page.rows) == 1
        assert page.rows[0][1] == "Bob"
    finally:
        conn.close()
