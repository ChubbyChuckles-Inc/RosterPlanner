from __future__ import annotations

import sqlite3
from typing import Generator, Optional, Tuple

import pytest
from PyQt6.QtWidgets import QApplication

from db.query_perf import create_instrumented_connection
from gui.services.schema_introspection_service import SchemaIntrospectionService
from gui.services.service_locator import services
from gui.viewmodels.data_preview_model import LazyDataPreviewModel
from gui.views.database_panel import DatabasePanel


@pytest.fixture
def qt_app() -> Generator[QApplication, None, None]:
    app = QApplication.instance() or QApplication([])
    yield app


def _build_services(
    conn: sqlite3.Connection,
) -> Tuple[SchemaIntrospectionService, LazyDataPreviewModel]:
    introspection = SchemaIntrospectionService(conn)
    introspection.refresh()
    preview_model = LazyDataPreviewModel(conn, introspection=introspection)
    return introspection, preview_model


def test_slow_query_log_viewer_records_queries(qt_app: QApplication) -> None:
    conn, logger = create_instrumented_connection(
        None,
        threshold_ms=0.0,
        max_records=50,
        log_enabled=False,
        check_same_thread=False,
    )
    preview_model: Optional[LazyDataPreviewModel] = None
    try:
        conn.execute("CREATE TABLE players (player_id INTEGER PRIMARY KEY, name TEXT)")
        conn.executemany(
            "INSERT INTO players VALUES (?, ?)",
            [(1, "Alpha"), (2, "Beta"), (3, "Gamma")],
        )
        conn.commit()
        introspection, preview_model = _build_services(conn)
        with services.override_context(
            schema_introspection_service=introspection,
            sqlite_conn=conn,
            data_preview_model=preview_model,
            query_performance_logger=logger,
            query_performance_threshold_ms=0.0,
        ):
            panel = DatabasePanel()
            qt_app.processEvents()
            if panel.table_list.count():
                panel.table_list.setCurrentRow(0)
                qt_app.processEvents()
            initial_rows = panel.slow_query_viewer.table.rowCount()
            panel.query_runner.sql_edit.setPlainText(
                "SELECT name FROM players WHERE name = 'Alpha'"
            )
            panel.query_runner.run_query()
            qt_app.processEvents()
            row_count = panel.slow_query_viewer.table.rowCount()
            assert row_count > initial_rows
            first_sql_item = panel.slow_query_viewer.table.item(0, 1)
            assert first_sql_item is not None
            assert "SELECT name FROM players WHERE name = 'Alpha'" in first_sql_item.toolTip()
            duration_texts = [
                panel.slow_query_viewer.table.item(row, 0).text()
                for row in range(row_count)
                if panel.slow_query_viewer.table.item(row, 0) is not None
            ]
            assert duration_texts
            assert any(text for text in duration_texts)
            assert "Showing" in panel.slow_query_viewer.status_label.text()
            panel.slow_query_viewer.clear_log()
            assert panel.slow_query_viewer.table.rowCount() == 0
            panel.deleteLater()
    finally:
        if preview_model is not None:
            preview_model.shutdown()
        conn.close()


def test_index_usage_advisor_flags_full_table_scan(qt_app: QApplication) -> None:
    conn, logger = create_instrumented_connection(
        None,
        threshold_ms=0.0,
        max_records=100,
        log_enabled=False,
        check_same_thread=False,
    )
    preview_model: Optional[LazyDataPreviewModel] = None
    try:
        conn.execute(
            "CREATE TABLE matches (match_id INTEGER PRIMARY KEY, opponent TEXT, score TEXT)"
        )
        conn.executemany(
            "INSERT INTO matches (opponent, score) VALUES (?, ?)",
            [(f"Opponent {i}", f"{i % 5}-{(i + 2) % 5}") for i in range(200)],
        )
        conn.commit()
        introspection, preview_model = _build_services(conn)
        logger.clear()
        with services.override_context(
            schema_introspection_service=introspection,
            sqlite_conn=conn,
            data_preview_model=preview_model,
            query_performance_logger=logger,
            query_performance_threshold_ms=0.0,
        ):
            panel = DatabasePanel()
            qt_app.processEvents()
            panel.query_runner.sql_edit.setPlainText(
                "SELECT opponent FROM matches WHERE opponent = 'Opponent 150'"
            )
            panel.query_runner.run_query()
            qt_app.processEvents()
            panel.index_advisor.refresh()
            advisory_rows = panel.index_advisor.table.rowCount()
            assert advisory_rows >= 1
            table_item = panel.index_advisor.table.item(0, 0)
            detail_item = panel.index_advisor.table.item(0, 2)
            assert table_item is not None
            assert table_item.text() == "matches"
            assert detail_item is not None
            assert "SCAN" in detail_item.text().upper()
            panel.deleteLater()
    finally:
        if preview_model is not None:
            preview_model.shutdown()
        conn.close()


def test_index_usage_advisor_skips_index_search(qt_app: QApplication) -> None:
    conn, logger = create_instrumented_connection(
        None,
        threshold_ms=0.0,
        max_records=100,
        log_enabled=False,
        check_same_thread=False,
    )
    preview_model: Optional[LazyDataPreviewModel] = None
    try:
        conn.execute(
            "CREATE TABLE players (player_id INTEGER PRIMARY KEY, name TEXT, rating INTEGER)"
        )
        conn.executemany(
            "INSERT INTO players (name, rating) VALUES (?, ?)",
            [(f"Player {i}", 1000 + i) for i in range(100)],
        )
        conn.commit()
        introspection, preview_model = _build_services(conn)
        logger.clear()
        with services.override_context(
            schema_introspection_service=introspection,
            sqlite_conn=conn,
            data_preview_model=preview_model,
            query_performance_logger=logger,
            query_performance_threshold_ms=0.0,
        ):
            panel = DatabasePanel()
            qt_app.processEvents()
            panel.query_runner.sql_edit.setPlainText(
                "SELECT name FROM players WHERE player_id = 10"
            )
            panel.query_runner.run_query()
            qt_app.processEvents()
            panel.index_advisor.refresh()
            assert panel.index_advisor.table.rowCount() == 0
            assert "No obvious missing index patterns" in panel.index_advisor.status_label.text()
            panel.deleteLater()
    finally:
        if preview_model is not None:
            preview_model.shutdown()
        conn.close()
