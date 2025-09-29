from __future__ import annotations

import sqlite3
import pytest
from PyQt6.QtWidgets import QApplication


@pytest.mark.parametrize("with_tables", [False, True])
def test_database_panel_creation(qtbot, with_tables):
    _ensure_app()
    try:
        from gui.views.database_panel import DatabasePanel
        from gui.services.service_locator import services as _services
    except Exception:
        pytest.skip("GUI components not available")

    conn = sqlite3.connect(":memory:")
    if with_tables:
        conn.execute("CREATE TABLE players (player_id INTEGER PRIMARY KEY, name TEXT NOT NULL)")
        conn.execute(
            "CREATE TABLE availability (availability_id INTEGER PRIMARY KEY, player_id INT, date TEXT, status TEXT)"
        )
    from gui.services.schema_introspection_service import SchemaIntrospectionService

    _services.register(
        "schema_introspection_service", SchemaIntrospectionService(conn), allow_override=True
    )

    panel = DatabasePanel()
    qtbot.addWidget(panel)
    names = [panel.table_list.item(i).text() for i in range(panel.table_list.count())]
    if with_tables:
        assert "players" in names and "availability" in names
    else:
        assert names == []


def test_database_panel_table_selection(qtbot):
    _ensure_app()
    try:
        from gui.views.database_panel import DatabasePanel
        from gui.services.service_locator import services as _services
    except Exception:
        pytest.skip("GUI components not available")

    conn = sqlite3.connect(":memory:")
    conn.execute(
        "CREATE TABLE test_table (id INTEGER PRIMARY KEY, value TEXT DEFAULT 'x', created_at TEXT)"
    )
    from gui.services.schema_introspection_service import SchemaIntrospectionService

    _services.register(
        "schema_introspection_service", SchemaIntrospectionService(conn), allow_override=True
    )
    panel = DatabasePanel()
    qtbot.addWidget(panel)
    if panel.table_list.count():
        panel.table_list.setCurrentRow(0)
        txt = panel.detail_label.text()
        assert "Table: test_table" in txt
        assert "Rows (cached):" in txt
        assert "• id: INTEGER" in txt
        assert "PK" in txt
        assert "• value: TEXT" in txt
        assert panel.graph_widget is not None


_app_instance = None


def _ensure_app():
    global _app_instance
    app = QApplication.instance()
    if app is None:
        app = QApplication([])
    _app_instance = app
    return app
