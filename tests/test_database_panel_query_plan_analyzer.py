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


def test_query_plan_analyzer_generates_plan(qt_app: QApplication) -> None:
    conn = sqlite3.connect(":memory:", check_same_thread=False)
    preview_model: Optional[LazyDataPreviewModel] = None
    try:
        conn.execute("CREATE TABLE players (player_id INTEGER PRIMARY KEY, name TEXT)")
        conn.execute("CREATE INDEX idx_players_name ON players(name)")
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
            if panel.table_list.count():
                panel.table_list.setCurrentRow(0)
                qt_app.processEvents()
            panel.query_plan_analyzer.sql_edit.setPlainText(
                "SELECT name FROM players WHERE name = 'Alpha'"
            )
            panel.query_plan_analyzer.run_analysis()
            qt_app.processEvents()
            tree = panel.query_plan_analyzer.plan_tree
            assert tree.topLevelItemCount() >= 1
            root = tree.topLevelItem(0)
            assert root is not None
            assert root.childCount() >= 1
            notes = [root.child(i).text(2) for i in range(root.childCount())]
            assert any(note for note in notes)
            assert "Analysed query" in panel.query_plan_analyzer.status_label.text()
            panel.deleteLater()
    finally:
        if preview_model is not None:
            preview_model.shutdown()
        conn.close()


def test_query_plan_analyzer_blocks_mutating_sql(qt_app: QApplication) -> None:
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
            if panel.table_list.count():
                panel.table_list.setCurrentRow(0)
                qt_app.processEvents()
            panel.query_plan_analyzer.sql_edit.setPlainText("UPDATE players SET name='Beta'")
            panel.query_plan_analyzer.run_analysis()
            assert "Only read-only" in panel.query_plan_analyzer.status_label.text()
            assert panel.query_plan_analyzer.plan_tree.topLevelItemCount() == 0
            panel.deleteLater()
    finally:
        if preview_model is not None:
            preview_model.shutdown()
        conn.close()
