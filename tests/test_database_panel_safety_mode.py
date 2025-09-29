import os
import sys

from typing import Generator, List, Optional

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
)


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
    def __init__(self, table_info: TableInfo):
        self._info = table_info

    def list_tables(self) -> List[str]:
        return [self._info.name]

    def get_table_info(self, table: str) -> Optional[TableInfo]:
        if table == self._info.name:
            return self._info
        return None


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
    fake_introspection = _FakeIntrospectionService(table_info)
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
