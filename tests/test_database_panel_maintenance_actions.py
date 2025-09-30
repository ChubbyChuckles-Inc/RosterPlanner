from __future__ import annotations

from datetime import datetime
from pathlib import Path
import sqlite3
from typing import Generator

import pytest
from PyQt6.QtWidgets import QApplication

from gui.services.service_locator import services
from gui.services.schema_introspection_service import SchemaIntrospectionService
from gui.services.foreign_key_orphan_detector import (
    ForeignKeyOrphanFinding,
    ForeignKeyOrphanReport,
)
from gui.views.database_panel import DatabasePanel
from gui.components.maintenance_actions import MaintenanceActionsWidget
from gui.components.chrome_dialog import ChromeDialog


class DummySafetyService:
    def __init__(self) -> None:
        self._enabled = False

    def admin_enabled(self) -> bool:
        return self._enabled

    def set_admin_enabled(self, enabled: bool) -> bool:
        changed = self._enabled != enabled
        self._enabled = enabled
        return changed


class RecordingConnection(sqlite3.Connection):
    def __init__(self, *args, **kwargs):  # type: ignore[no-untyped-def]
        super().__init__(*args, **kwargs)
        self.statements: list[str] = []

    def execute(self, sql, *args, **kwargs):  # type: ignore[no-untyped-def]
        self.statements.append(str(sql).strip().upper())
        return super().execute(sql, *args, **kwargs)


@pytest.fixture
def qt_app() -> Generator[QApplication, None, None]:
    app = QApplication.instance() or QApplication([])
    yield app


@pytest.fixture
def safety_service() -> DummySafetyService:
    return DummySafetyService()


@pytest.fixture
def recording_connection() -> RecordingConnection:
    conn = sqlite3.connect(":memory:", factory=RecordingConnection)
    conn.execute("CREATE TABLE sample(id INTEGER PRIMARY KEY, value TEXT)")
    conn.commit()
    return conn  # type: ignore[return-value]


def _build_panel(
    qt_app: QApplication,
    safety_service: DummySafetyService,
    conn: sqlite3.Connection,
) -> DatabasePanel:
    with services.override_context(
        database_safety_service=safety_service,
        sqlite_conn=conn,
    ):
        panel = DatabasePanel()
        qt_app.processEvents()
    return panel


def test_vacuum_button_admin_gated(
    qt_app: QApplication,
    safety_service: DummySafetyService,
    recording_connection: RecordingConnection,
) -> None:
    panel = _build_panel(qt_app, safety_service, recording_connection)
    try:
        qt_app.processEvents()
        assert not panel.maintenance_actions.run_button.isEnabled()
        panel.admin_toggle.setChecked(True)
        qt_app.processEvents()
        assert panel.maintenance_actions.run_button.isEnabled()
    finally:
        panel.deleteLater()
        recording_connection.close()


def test_vacuum_runs_statements(
    qt_app: QApplication,
    monkeypatch: pytest.MonkeyPatch,
    safety_service: DummySafetyService,
    recording_connection: RecordingConnection,
) -> None:
    panel = _build_panel(qt_app, safety_service, recording_connection)
    try:
        panel.admin_toggle.setChecked(True)
        qt_app.processEvents()

        monkeypatch.setattr(panel.maintenance_actions, "_confirm_maintenance", lambda: True)
        captured: dict[str, str] = {}

        def _capture_notice(timestamp: str) -> None:
            captured["ts"] = timestamp

        monkeypatch.setattr(panel.maintenance_actions, "_show_completion_notice", _capture_notice)
        monkeypatch.setattr(panel.maintenance_actions, "_show_error_dialog", lambda _msg: None)

        panel.maintenance_actions.run_button.click()
        qt_app.processEvents()

        executed = recording_connection.statements
        assert "VACUUM" in executed
        assert "ANALYZE" in executed
        assert "MAINTENANCE COMPLETED" in panel.maintenance_actions.status_label.text().upper()
        assert "ts" in captured
    finally:
        panel.deleteLater()
        recording_connection.close()


def test_vacuum_cancelled_does_not_execute(
    qt_app: QApplication,
    monkeypatch: pytest.MonkeyPatch,
    safety_service: DummySafetyService,
    recording_connection: RecordingConnection,
) -> None:
    panel = _build_panel(qt_app, safety_service, recording_connection)
    try:
        panel.admin_toggle.setChecked(True)
        qt_app.processEvents()

        monkeypatch.setattr(panel.maintenance_actions, "_confirm_maintenance", lambda: False)
        monkeypatch.setattr(panel.maintenance_actions, "_show_completion_notice", lambda _ts: None)

        panel.maintenance_actions.run_button.click()
        qt_app.processEvents()

        executed = [
            stmt for stmt in recording_connection.statements if stmt in {"VACUUM", "ANALYZE"}
        ]
        assert not executed
        assert "CANCELLED" in panel.maintenance_actions.status_label.text().upper()
    finally:
        panel.deleteLater()
        recording_connection.close()


def test_maintenance_dialogs_use_chrome(qt_app: QApplication) -> None:
    widget = MaintenanceActionsWidget()
    try:
        confirm = widget._build_confirm_dialog()
        assert isinstance(confirm, ChromeDialog)
        confirm.deleteLater()
        complete = widget._build_completion_dialog("2025-09-30 12:34:56 UTC")
        assert isinstance(complete, ChromeDialog)
        complete.deleteLater()
    finally:
        widget.deleteLater()


def test_confirm_dialog_handles_deleted_qt_object(
    qt_app: QApplication, monkeypatch: pytest.MonkeyPatch
) -> None:
    widget = MaintenanceActionsWidget()

    class _FakeDialog:
        Accepted = 1

        def __init__(self) -> None:
            self._after_exec = False

        def exec(self) -> int:
            self._after_exec = True
            return 1

        def __getattr__(self, item: str):  # type: ignore[no-untyped-def]
            if self._after_exec:
                raise RuntimeError("dialog deleted")
            raise AttributeError(item)

    try:
        monkeypatch.setattr(widget, "_build_confirm_dialog", lambda: _FakeDialog())
        assert widget._confirm_maintenance()
    finally:
        widget.deleteLater()


def test_database_panel_fk_orphan_widget_integration(
    qt_app: QApplication,
    safety_service: DummySafetyService,
    recording_connection: RecordingConnection,
    tmp_path: Path,
) -> None:
    # Prepare schema with a simple foreign key relationship.
    recording_connection.execute("PRAGMA foreign_keys=ON")
    recording_connection.execute("CREATE TABLE parent(id INTEGER PRIMARY KEY)")
    recording_connection.execute(
        "CREATE TABLE child(id INTEGER PRIMARY KEY, parent_id INTEGER, "
        "FOREIGN KEY(parent_id) REFERENCES parent(id))"
    )
    recording_connection.execute("PRAGMA foreign_keys=OFF")
    recording_connection.execute("INSERT INTO child(id, parent_id) VALUES (1, 99)")
    recording_connection.execute("PRAGMA foreign_keys=ON")
    recording_connection.commit()

    schema = SchemaIntrospectionService(recording_connection)

    finding = ForeignKeyOrphanFinding(
        table="child",
        columns=("parent_id",),
        ref_table="parent",
        ref_columns=("id",),
        orphan_count=1,
        sample_rows=("parent_id=99",),
    )
    report = ForeignKeyOrphanReport((finding,), datetime.utcnow(), 0.0)

    class _Detector:
        def __init__(self) -> None:
            self.calls = 0

        def scan(self, *, sample_limit: int = 10) -> ForeignKeyOrphanReport:
            self.calls += 1
            return report

        def format_report(self, result: ForeignKeyOrphanReport) -> str:
            return "panel report"

    detector = _Detector()
    export_path = tmp_path / "fk_report.txt"

    with services.override_context(
        database_safety_service=safety_service,
        sqlite_conn=recording_connection,
        schema_introspection_service=schema,
    ):
        panel = DatabasePanel()
        qt_app.processEvents()
    try:
        panel.fk_orphan_widget.set_detector(detector)
        panel.fk_orphan_widget.set_file_saver(lambda: str(export_path))
        panel.fk_orphan_widget.scan_button.click()
        qt_app.processEvents()
        assert detector.calls == 1
        assert panel.fk_orphan_widget.table.rowCount() == 1
        assert panel.fk_orphan_widget.export_button.isEnabled()

        panel.fk_orphan_widget.export_button.click()
        qt_app.processEvents()
        assert export_path.read_text(encoding="utf-8") == "panel report"
    finally:
        panel.deleteLater()
        recording_connection.close()
