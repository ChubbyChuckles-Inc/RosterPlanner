from __future__ import annotations

from datetime import datetime
from pathlib import Path
from typing import Generator

import pytest
from PyQt6.QtWidgets import QApplication

from gui.components.foreign_key_orphan_widget import ForeignKeyOrphanWidget
from gui.services.foreign_key_orphan_detector import ForeignKeyOrphanFinding, ForeignKeyOrphanReport


@pytest.fixture
def qt_app() -> Generator[QApplication, None, None]:
    app = QApplication.instance() or QApplication([])
    yield app


class _DummyDetector:
    def __init__(self, report: ForeignKeyOrphanReport, formatted: str = "report") -> None:
        self._report = report
        self._formatted = formatted
        self.scan_calls = 0

    def scan(self, *, sample_limit: int = 10) -> ForeignKeyOrphanReport:
        self.scan_calls += 1
        return self._report

    def format_report(self, report: ForeignKeyOrphanReport) -> str:
        return self._formatted


def test_orphan_widget_populates_and_exports(tmp_path: Path, qt_app: QApplication) -> None:
    finding = ForeignKeyOrphanFinding(
        table="child",
        columns=("parent_id",),
        ref_table="parent",
        ref_columns=("id",),
        orphan_count=3,
        sample_rows=("parent_id=10", "parent_id=11"),
    )
    report = ForeignKeyOrphanReport((finding,), datetime.utcnow(), 0.01)
    detector = _DummyDetector(report, formatted="dummy report text")

    widget = ForeignKeyOrphanWidget()
    widget.set_detector(detector)
    widget.set_file_saver(lambda: str(tmp_path / "orphan.txt"))
    try:
        widget.scan_button.click()
        qt_app.processEvents()
        assert detector.scan_calls == 1
        assert widget.table.rowCount() == 1
        assert widget.export_button.isEnabled()

        widget.export_button.click()
        qt_app.processEvents()
        output = (tmp_path / "orphan.txt").read_text(encoding="utf-8")
        assert "dummy report text" in output
    finally:
        widget.deleteLater()


def test_orphan_widget_handles_missing_detector(qt_app: QApplication) -> None:
    widget = ForeignKeyOrphanWidget()
    widget.set_detector(None)
    try:
        widget.scan_button.click()
        qt_app.processEvents()
        assert widget.table.rowCount() == 0
        assert not widget.export_button.isEnabled()
    finally:
        widget.deleteLater()
