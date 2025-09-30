"""Foreign key orphan detector widget for the Database panel (Milestone 7.11.16).

The widget provides an operator-friendly interface to scan the active
SQLite database for rows that violate foreign key expectations. Findings
are displayed in a compact table and can be exported as a text report
for audit or bug-report purposes. The widget is read-only and can be
used in the Database panel regardless of admin mode.
"""

from __future__ import annotations

from typing import Callable, Optional
from datetime import datetime
import sqlite3

from PyQt6.QtWidgets import (
    QFileDialog,
    QLabel,
    QPushButton,
    QTableWidget,
    QTableWidgetItem,
    QHBoxLayout,
    QVBoxLayout,
    QWidget,
)

try:  # pragma: no cover - optional theme integration
    from gui.components.theme_aware import ThemeAwareMixin  # type: ignore
except Exception:  # pragma: no cover

    class ThemeAwareMixin:  # type: ignore
        def apply_theme(self) -> None:
            return


from gui.services.service_locator import services
from gui.services.schema_introspection_service import SchemaIntrospectionService
from gui.services.foreign_key_orphan_detector import (
    ForeignKeyOrphanDetector,
    ForeignKeyOrphanReport,
)

__all__ = ["ForeignKeyOrphanWidget"]


class ForeignKeyOrphanWidget(QWidget, ThemeAwareMixin):
    """Widget that surfaces foreign key orphan scan results."""

    def __init__(
        self,
        parent: Optional[QWidget] = None,
        *,
        detector: Optional[ForeignKeyOrphanDetector] = None,
        schema_service: Optional[SchemaIntrospectionService] = None,
        connection: Optional[sqlite3.Connection] = None,
    ) -> None:
        super().__init__(parent)
        self.setObjectName("dbForeignKeyOrphanWidget")
        self._detector = detector
        self._schema_service = schema_service
        self._connection = connection
        self._latest_report: Optional[ForeignKeyOrphanReport] = None
        self._file_saver: Callable[[], Optional[str]] = self._prompt_for_export_path

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(4)

        header = QLabel("Foreign key orphan scan")
        header.setObjectName("dbFkOrphanHeader")
        layout.addWidget(header)

        description = QLabel(
            "Detects rows whose foreign key references no longer exist. "
            "Ideally this list is empty; any findings should be investigated."
        )
        description.setWordWrap(True)
        description.setObjectName("dbFkOrphanDescription")
        layout.addWidget(description)

        button_row = QHBoxLayout()
        button_row.setContentsMargins(0, 0, 0, 0)
        button_row.setSpacing(6)

        self.scan_button = QPushButton("Scan for orphans", self)
        self.scan_button.setObjectName("dbFkOrphanScanButton")
        self.scan_button.clicked.connect(self._on_scan_clicked)  # type: ignore[arg-type]
        button_row.addWidget(self.scan_button)

        self.export_button = QPushButton("Export report", self)
        self.export_button.setObjectName("dbFkOrphanExportButton")
        self.export_button.setEnabled(False)
        self.export_button.clicked.connect(self._on_export_clicked)  # type: ignore[arg-type]
        button_row.addWidget(self.export_button)

        button_row.addStretch(1)
        layout.addLayout(button_row)

        self.table = QTableWidget(0, 5, self)
        self.table.setObjectName("dbFkOrphanTable")
        self.table.setHorizontalHeaderLabels(
            ["Table", "Columns", "References", "Orphan rows", "Sample values"]
        )
        self.table.verticalHeader().setVisible(False)
        self.table.setSortingEnabled(True)
        self.table.setAlternatingRowColors(True)
        self.table.setMinimumHeight(120)
        layout.addWidget(self.table)

        self.status_label = QLabel("No scan performed yet.")
        self.status_label.setObjectName("dbFkOrphanStatus")
        self.status_label.setWordWrap(True)
        layout.addWidget(self.status_label)

    # ------------------------------------------------------------------
    def set_detector(self, detector: ForeignKeyOrphanDetector | None) -> None:
        """Inject a custom detector instance (primarily for tests)."""

        self._detector = detector

    def set_schema_service(self, service: SchemaIntrospectionService | None) -> None:
        """Assign the schema introspection service used for scanning."""

        self._schema_service = service
        self._detector = None  # force lazy re-instantiation

    def set_connection(self, connection: sqlite3.Connection | None) -> None:
        """Assign the SQLite connection backing scans."""

        self._connection = connection
        self._detector = None

    def set_file_saver(self, saver: Callable[[], Optional[str]]) -> None:
        """Override the file saving callback (used by tests)."""

        self._file_saver = saver

    # ------------------------------------------------------------------
    def _ensure_detector(self) -> Optional[ForeignKeyOrphanDetector]:
        if self._detector is not None:
            return self._detector
        if self._schema_service is None:
            self._schema_service = services.try_get("schema_introspection_service")
        if self._connection is None:
            self._connection = services.try_get("sqlite_conn")
        # Allow pre-registered detector override via service locator.
        if self._detector is None:
            existing = services.try_get("foreign_key_orphan_detector")
            if isinstance(existing, ForeignKeyOrphanDetector):
                self._detector = existing
        if (
            self._detector is None
            and self._connection is not None
            and self._schema_service is not None
        ):
            try:
                self._detector = ForeignKeyOrphanDetector(self._connection, self._schema_service)
            except Exception:
                self._detector = None
        return self._detector

    def _on_scan_clicked(self) -> None:
        detector = self._ensure_detector()
        if detector is None:
            self._latest_report = None
            self._populate_table(None)
            self.export_button.setEnabled(False)
            self._set_status("Foreign key scan unavailable (detector missing).", is_error=True)
            return
        report = detector.scan()
        self._latest_report = report
        self._populate_table(report)
        has_findings = bool(report.findings)
        self.export_button.setEnabled(has_findings)
        if has_findings:
            self._set_status(
                f"Found {len(report.findings)} orphan constraint(s) totalling {report.total_orphans()} row(s)."
            )
        else:
            self._set_status("No orphaned foreign key references detected.")

    def _on_export_clicked(self) -> None:
        if self._latest_report is None or not self._latest_report.findings:
            self._set_status("Nothing to export. Run a scan first.", is_error=True)
            return
        path = self._file_saver()
        if not path:
            self._set_status("Export cancelled.")
            return
        detector = self._ensure_detector()
        if detector is None:
            self._set_status("Unable to export: detector unavailable.", is_error=True)
            return
        try:
            text = detector.format_report(self._latest_report)
            with open(path, "w", encoding="utf-8") as handle:
                handle.write(text)
        except Exception as exc:  # pragma: no cover - IO failures
            self._set_status(f"Failed to export report: {exc}", is_error=True)
            return
        self._set_status(f"Exported report to {path}.")

    # ------------------------------------------------------------------
    def _populate_table(self, report: ForeignKeyOrphanReport | None) -> None:
        self.table.setSortingEnabled(False)
        self.table.setRowCount(0)
        if report is not None and report.findings:
            for finding in report.findings:
                row = self.table.rowCount()
                self.table.insertRow(row)
                self.table.setItem(row, 0, QTableWidgetItem(finding.table))
                self.table.setItem(row, 1, QTableWidgetItem(", ".join(finding.columns)))
                ref_text = f"{finding.ref_table} ({', '.join(finding.ref_columns)})"
                self.table.setItem(row, 2, QTableWidgetItem(ref_text))
                self.table.setItem(row, 3, QTableWidgetItem(str(finding.orphan_count)))
                samples_text = "\n".join(finding.sample_rows[:5])
                self.table.setItem(row, 4, QTableWidgetItem(samples_text))
        self.table.setSortingEnabled(True)

    def _set_status(self, message: str, *, is_error: bool = False) -> None:
        prefix = "⚠ " if is_error else ""
        timestamp = datetime.utcnow().strftime("%H:%M:%S")
        self.status_label.setText(f"[{timestamp}] {prefix}{message}")

    def _prompt_for_export_path(self) -> Optional[str]:  # pragma: no cover - interactive dialog
        path, _filter = QFileDialog.getSaveFileName(
            self,
            "Export foreign key orphan report",
            "fk_orphan_report.txt",
            "Text Files (*.txt);;All Files (*)",
        )
        return path or None
