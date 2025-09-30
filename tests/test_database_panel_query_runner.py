from __future__ import annotations

import sqlite3
from typing import Generator, Optional

import pytest
from PyQt6.QtWidgets import QApplication

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
) -> tuple[SchemaIntrospectionService, LazyDataPreviewModel]:
    introspection = SchemaIntrospectionService(conn)
    introspection.refresh()
    preview_model = LazyDataPreviewModel(conn, introspection=introspection)
    return introspection, preview_model


def test_query_runner_executes_select(qt_app: QApplication):
    conn = sqlite3.connect(":memory:", check_same_thread=False)
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
        ):
            panel = DatabasePanel()
            qt_app.processEvents()
            panel.table_list.setCurrentRow(0)
            qt_app.processEvents()
            panel.query_runner.sql_edit.setPlainText("SELECT name FROM players ORDER BY player_id")
            panel.query_runner.run_query()
            qt_app.processEvents()
            assert panel.query_runner.result_table.rowCount() == 3
            assert panel.query_runner.result_table.columnCount() == 1
            names = [
                panel.query_runner.result_table.item(row, 0).text()
                for row in range(panel.query_runner.result_table.rowCount())
            ]
            assert names == ["Alpha", "Beta", "Gamma"]
    finally:
        if preview_model is not None:
            preview_model.shutdown()
        conn.close()


def test_query_runner_blocks_mutating_sql(qt_app: QApplication):
    conn = sqlite3.connect(":memory:", check_same_thread=False)
    preview_model: Optional[LazyDataPreviewModel] = None
    try:
        conn.execute("CREATE TABLE players (player_id INTEGER PRIMARY KEY, name TEXT)")
        conn.execute("INSERT INTO players VALUES (1, 'Alpha')")
        conn.commit()
        introspection, preview_model = _build_services(conn)
        with services.override_context(
            schema_introspection_service=introspection,
            sqlite_conn=conn,
            data_preview_model=preview_model,
        ):
            panel = DatabasePanel()
            qt_app.processEvents()
            panel.table_list.setCurrentRow(0)
            qt_app.processEvents()
            panel.query_runner.sql_edit.setPlainText("DELETE FROM players")
            panel.query_runner.run_query()
            assert "Only read-only queries" in panel.query_runner.status_label.text()
            post_count = conn.execute("SELECT COUNT(*) FROM players").fetchone()[0]
            assert post_count == 1
    finally:
        if preview_model is not None:
            preview_model.shutdown()
        conn.close()
