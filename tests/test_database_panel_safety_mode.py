import os
import sqlite3
import sys

from typing import Dict, Generator, List, Optional

import pytest
from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import QApplication

from gui.services.service_locator import services
from gui.views.database_panel import DatabasePanel
from gui.services.schema_introspection_service import (
    TableInfo,
    ColumnInfo,
    ForeignKeyInfo,
    IndexInfo,
    ColumnStats,
    SchemaIntrospectionService,
)
from gui.viewmodels.data_preview_model import LazyDataPreviewModel


def _app() -> QApplication:
    os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
    return QApplication.instance() or QApplication(sys.argv[:1])


class _FakeSafetyService:
    def __init__(self, enabled: bool = False) -> None:
        self.state = enabled
        self.set_calls: list[bool] = []

    def admin_enabled(self) -> bool:
        return self.state

    def set_admin_enabled(self, enabled: bool) -> bool:
        changed = self.state != enabled
        self.state = enabled
        self.set_calls.append(enabled)
        return changed


class _FakeIntrospectionService:
    def __init__(
        self, table_info: TableInfo, stats: Optional[Dict[str, ColumnStats]] = None
    ) -> None:
        self._info = table_info
        self._stats = stats or {}

    def list_tables(self) -> List[str]:
        return [self._info.name]

    def get_table_info(self, table: str) -> Optional[TableInfo]:
        if table == self._info.name:
            return self._info
        return None

    def get_column_stats(self, table: str) -> Dict[str, ColumnStats]:
        if table == self._info.name:
            return dict(self._stats)
        return {}


@pytest.fixture
def qt_app() -> Generator[QApplication, None, None]:
    app = _app()
    yield app


def test_database_panel_defaults_to_read_only(qt_app: QApplication):
    fake_service = _FakeSafetyService(False)
    with services.override_context(database_safety_service=fake_service):
        panel = DatabasePanel()
        assert panel.is_admin_mode() is False
        assert panel.admin_toggle.isChecked() is False
        assert fake_service.set_calls == []
        assert "READ-ONLY" in panel.banner.text()
        assert panel.admin_actions.isHidden() is True
        assert panel.admin_notice.isHidden() is False


def test_database_panel_toggle_enables_admin_mode(qt_app: QApplication):
    fake_service = _FakeSafetyService(False)
    with services.override_context(database_safety_service=fake_service):
        panel = DatabasePanel()
        panel.admin_toggle.setCheckState(Qt.CheckState.Checked)
        qt_app.processEvents()
        assert panel.is_admin_mode() is True
        assert fake_service.state is True
        assert fake_service.set_calls[-1] is True
        assert panel.admin_actions.isHidden() is False
        assert panel.admin_notice.isHidden() is True
        assert "ADMIN" in panel.banner.text()


def test_database_panel_respects_persisted_admin_state(qt_app: QApplication):
    fake_service = _FakeSafetyService(True)
    with services.override_context(database_safety_service=fake_service):
        panel = DatabasePanel()
        assert panel.is_admin_mode() is True
        assert panel.admin_toggle.isChecked() is True
        assert panel.admin_actions.isHidden() is False
        assert panel.admin_notice.isHidden() is True
        assert "ADMIN" in panel.banner.text()


def test_database_panel_shows_table_profile_summary(qt_app: QApplication):
    fake_service = _FakeSafetyService(False)
    table_info = TableInfo(
        name="team",
        columns=[
            ColumnInfo(name="team_id", type="INTEGER", not_null=True, default=None, pk_position=1),
            ColumnInfo(
                name="division_id", type="INTEGER", not_null=False, default=None, pk_position=0
            ),
            ColumnInfo(name="name", type="TEXT", not_null=False, default=None, pk_position=0),
        ],
        primary_key=["team_id"],
        foreign_keys=[
            ForeignKeyInfo(
                constraint_id=1,
                sequence=0,
                column="division_id",
                ref_table="division",
                ref_column="division_id",
                on_update="NO ACTION",
                on_delete="CASCADE",
                match="NONE",
            )
        ],
        indexes=[IndexInfo(name="idx_team_name", unique=False, columns=["name"])],
        row_count=42,
        approx_page_count=12,
        approx_size_bytes=49152,
        last_ingested_at="2025-09-29T12:34:56",
    )
    stats_map = {
        "team_id": ColumnStats(
            sample_rows=10,
            distinct_count=10,
            null_fraction=0.0,
            min_value="1",
            max_value="10",
        ),
        "division_id": ColumnStats(
            sample_rows=10,
            distinct_count=3,
            null_fraction=20.0,
            min_value="100",
            max_value="300",
        ),
        "name": ColumnStats(
            sample_rows=10,
            distinct_count=9,
            null_fraction=10.0,
            min_value=None,
            max_value=None,
        ),
    }
    fake_introspection = _FakeIntrospectionService(table_info, stats_map)
    with services.override_context(
        database_safety_service=fake_service,
        schema_introspection_service=fake_introspection,
    ):
        panel = DatabasePanel()
        panel.table_list.setCurrentRow(0)
        qt_app.processEvents()
        text = panel.detail_label.text()
        assert "Table Profile" in text
        assert "Rows: 42" in text
        assert "Size: 12 pages" in text
        assert "~48.0 KB" in text
        assert "Last ingest:" in text
    assert "Stats: distinct≈10, null≈0.0%, range: 1 ↔ 10, n=10" in text
    assert "Stats: distinct≈3, null≈20.0%, range: 100 ↔ 300, n=10" in text
    assert "Stats: distinct≈9, null≈10.0%, n=10" in text


def test_database_panel_quick_filter_updates_preview(qt_app: QApplication):
    conn = sqlite3.connect(":memory:", check_same_thread=False)
    preview_model: Optional[LazyDataPreviewModel] = None
    try:
        conn.execute("CREATE TABLE players (player_id INTEGER PRIMARY KEY, name TEXT, notes TEXT)")
        conn.executemany(
            "INSERT INTO players VALUES (?, ?, ?)",
            [
                (1, "Alpha", "Captain"),
                (2, "Beta", "Bench"),
                (3, "Gamma", "Reserve"),
            ],
        )
        conn.commit()
        introspection = SchemaIntrospectionService(conn)
        introspection.refresh()
        preview_model = LazyDataPreviewModel(conn, introspection=introspection)
        fake_service = _FakeSafetyService(False)
        with services.override_context(
            database_safety_service=fake_service,
            schema_introspection_service=introspection,
            data_preview_model=preview_model,
        ):
            panel = DatabasePanel()
            try:
                panel.table_list.setCurrentRow(0)
                qt_app.processEvents()
                initial_text = panel.detail_label.text()
                assert "Preview rows:" in initial_text
                assert "Alpha" in initial_text

                panel.quick_filter_input.setText("Beta")
                qt_app.processEvents()
                panel._filter_timer.stop()
                panel._refresh_details_for_current_table()
                filtered_text = panel.detail_label.text()
                assert "filter: Beta" in filtered_text
                assert "Beta" in filtered_text
                assert "Alpha" not in filtered_text
                diff_text = panel.row_diff_viewer._diff_view.toPlainText()
                assert "Need at least two rows" in diff_text
            finally:
                panel.deleteLater()
    finally:
        if preview_model is not None:
            preview_model.shutdown()
        conn.close()


def test_row_detail_inspector_shows_json_and_related(qt_app: QApplication):
    conn = sqlite3.connect(":memory:", check_same_thread=False)
    preview_model: Optional[LazyDataPreviewModel] = None
    try:
        conn.execute("CREATE TABLE division (division_id INTEGER PRIMARY KEY, name TEXT)")
        conn.execute(
            "CREATE TABLE team (team_id INTEGER PRIMARY KEY, division_id INTEGER REFERENCES division(division_id), name TEXT)"
        )
        conn.execute("INSERT INTO division (division_id, name) VALUES (1, 'Test Division')")
        conn.execute("INSERT INTO team (team_id, division_id, name) VALUES (10, 1, 'Alpha Team')")
        conn.commit()

        introspection = SchemaIntrospectionService(conn)
        introspection.refresh()
        preview_model = LazyDataPreviewModel(conn, introspection=introspection)
        fake_service = _FakeSafetyService(False)

        with services.override_context(
            database_safety_service=fake_service,
            schema_introspection_service=introspection,
            data_preview_model=preview_model,
        ):
            panel = DatabasePanel()
            qt_app.processEvents()
            for row in range(panel.table_list.count()):
                item = panel.table_list.item(row)
                if item and item.text() == "team":
                    panel.table_list.setCurrentRow(row)
                    break
            qt_app.processEvents()
            assert panel.row_inspector.row_selector.count() >= 1
            json_text = panel.row_inspector.json_view.toPlainText()
            assert '"team_id": 10' in json_text
            assert '"division_id": 1' in json_text
            assert '"name": "Alpha Team"' in json_text
            related_html = panel.row_inspector.related_label.text()
            assert "division" in related_html
            assert "Preview:" in related_html
            panel.deleteLater()
    finally:
        if preview_model is not None:
            preview_model.shutdown()
        conn.close()


def test_row_diff_viewer_highlights_differences(qt_app: QApplication):
    conn = sqlite3.connect(":memory:", check_same_thread=False)
    preview_model: Optional[LazyDataPreviewModel] = None
    try:
        conn.execute("CREATE TABLE players (player_id INTEGER PRIMARY KEY, name TEXT, notes TEXT)")
        conn.executemany(
            "INSERT INTO players VALUES (?, ?, ?)",
            [
                (1, "Alpha", "Captain"),
                (2, "Beta", "Bench"),
            ],
        )
        conn.commit()
        introspection = SchemaIntrospectionService(conn)
        introspection.refresh()
        preview_model = LazyDataPreviewModel(conn, introspection=introspection)
        fake_service = _FakeSafetyService(False)

        with services.override_context(
            database_safety_service=fake_service,
            schema_introspection_service=introspection,
            data_preview_model=preview_model,
        ):
            panel = DatabasePanel()
            qt_app.processEvents()
            panel.table_list.setCurrentRow(0)
            qt_app.processEvents()
            assert panel.row_diff_viewer._base_selector.count() >= 2
            assert panel.row_diff_viewer._compare_selector.count() >= 2
            diff_text = panel.row_diff_viewer._diff_view.toPlainText()
            assert "Comparing Row 1 vs Row 2" in diff_text
            assert "name: → Alpha -> Beta" in diff_text
            panel.deleteLater()
    finally:
        if preview_model is not None:
            preview_model.shutdown()
        conn.close()
