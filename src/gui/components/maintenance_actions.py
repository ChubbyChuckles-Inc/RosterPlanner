"""Maintenance actions for database upkeep tasks.

Provides an admin-gated widget that can trigger VACUUM/ANALYZE operations on
an attached SQLite connection with lightweight status reporting.
"""

from __future__ import annotations

import logging
import sqlite3
from datetime import datetime
from typing import Optional

from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import (
    QApplication,
    QDialog,
    QHBoxLayout,
    QLabel,
    QMessageBox,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

try:  # pragma: no cover - optional theme integration
    from gui.components.theme_aware import ThemeAwareMixin  # type: ignore
except Exception:  # pragma: no cover

    class ThemeAwareMixin:  # type: ignore
        def apply_theme(self) -> None:
            return


try:  # pragma: no cover - chrome dialog available in GUI runtime
    from gui.components.chrome_dialog import ChromeDialog  # type: ignore
except Exception:  # pragma: no cover
    ChromeDialog = None  # type: ignore[assignment]


_LOGGER = logging.getLogger(__name__)

__all__ = ["MaintenanceActionsWidget"]


class MaintenanceActionsWidget(QWidget, ThemeAwareMixin):
    """Admin-only maintenance controls for database housekeeping."""

    def __init__(self, parent: Optional[QWidget] = None) -> None:
        super().__init__(parent)
        self.setObjectName("dbMaintenanceActions")
        self._conn: Optional[sqlite3.Connection] = None
        self._admin_enabled = False

        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(6)

        intro = QLabel("Run VACUUM/ANALYZE to compact the database and refresh planner statistics.")
        intro.setWordWrap(True)
        intro.setObjectName("dbMaintenanceIntro")
        root.addWidget(intro)

        button_row = QHBoxLayout()
        button_row.setContentsMargins(0, 0, 0, 0)
        button_row.setSpacing(6)

        self.run_button = QPushButton("Run VACUUM & ANALYZE", self)
        self.run_button.setObjectName("dbMaintenanceRun")
        self.run_button.setEnabled(False)
        self.run_button.clicked.connect(self._on_run_clicked)  # type: ignore[arg-type]
        self.run_button.setToolTip(
            "Performs SQLite VACUUM and ANALYZE commands. Requires admin mode and may take time."
        )
        button_row.addWidget(self.run_button)
        button_row.addStretch(1)
        root.addLayout(button_row)

        self.status_label = QLabel("Maintenance idle.", self)
        self.status_label.setObjectName("dbMaintenanceStatus")
        self.status_label.setWordWrap(True)
        root.addWidget(self.status_label)

        self.apply_theme()

    # ------------------------------------------------------------------
    def apply_theme(self) -> None:  # pragma: no cover - styling hook stub
        parent_apply = getattr(super(), "apply_theme", None)
        if callable(parent_apply):
            try:
                parent_apply()
            except Exception:
                pass

    # ------------------------------------------------------------------
    def set_connection(self, conn: Optional[sqlite3.Connection]) -> None:
        """Assign the SQLite connection to operate on."""

        self._conn = conn
        self._update_enabled_state()

    def set_admin_enabled(self, enabled: bool) -> None:
        """Update admin gating state."""

        self._admin_enabled = enabled
        self._update_enabled_state()

    # ------------------------------------------------------------------
    def _on_run_clicked(self) -> None:
        if not self._conn:
            self._set_status("Maintenance unavailable: missing connection.")
            return
        if not self._confirm_maintenance():
            self._set_status("Maintenance cancelled.")
            return
        self.run_button.setEnabled(False)
        QApplication.setOverrideCursor(Qt.CursorShape.BusyCursor)
        self._set_status("Maintenance running…")
        QApplication.processEvents()
        try:
            self._run_vacuum_analyze(self._conn)
        except Exception as exc:  # pragma: no cover - error path exercised in tests
            _LOGGER.exception("Maintenance run failed: %s", exc)
            if ChromeDialog is None:
                QMessageBox.critical(
                    self,
                    "Maintenance failed",
                    f"VACUUM/ANALYZE failed: {exc}",
                )
            else:
                self._show_error_dialog(f"VACUUM/ANALYZE failed: {exc}")
            self._set_status("Maintenance failed. See logs for details.")
        else:
            finished = datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S UTC")
            self._show_completion_notice(finished)
            self._set_status(f"Maintenance completed at {finished}.")
        finally:
            QApplication.restoreOverrideCursor()
            self._update_enabled_state()

    # ------------------------------------------------------------------
    def _update_enabled_state(self) -> None:
        has_conn = self._conn is not None
        self.run_button.setEnabled(self._admin_enabled and has_conn)
        if not has_conn:
            self._set_status("Maintenance unavailable: no SQLite connection configured.")

    @staticmethod
    def _run_vacuum_analyze(conn: sqlite3.Connection) -> None:
        conn.commit()
        conn.execute("VACUUM")
        conn.commit()
        conn.execute("ANALYZE")
        conn.commit()

    def _set_status(self, text: str) -> None:
        self.status_label.setText(text)

    # ------------------------------------------------------------------
    def _confirm_maintenance(self) -> bool:
        """Display a confirmation dialog and return True when the user proceeds."""

        dialog = self._build_confirm_dialog()
        if isinstance(dialog, QMessageBox):
            return dialog.exec() == QMessageBox.StandardButton.Yes
        accepted = getattr(type(dialog), "Accepted", QDialog.DialogCode.Accepted)
        result = dialog.exec()
        return result == int(accepted)

    def _build_confirm_dialog(self) -> QDialog:
        """Construct the maintenance confirmation dialog.

        Returns a ChromeDialog when available, falling back to QMessageBox otherwise.
        """

        message = "Running VACUUM/ANALYZE will lock the database connection temporarily. Proceed?"
        if ChromeDialog is None:
            box = QMessageBox(self)
            box.setIcon(QMessageBox.Icon.Question)
            box.setWindowTitle("Run VACUUM/ANALYZE")
            box.setText(message)
            box.setStandardButtons(QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No)
            box.setDefaultButton(QMessageBox.StandardButton.No)
            return box
        dialog = ChromeDialog(self, title="Run VACUUM/ANALYZE")
        layout = dialog.content_layout()
        prompt = QLabel(message, dialog)
        prompt.setWordWrap(True)
        layout.addWidget(prompt)
        button_row = QHBoxLayout()
        button_row.setContentsMargins(0, 0, 0, 0)
        button_row.setSpacing(8)
        button_row.addStretch(1)
        cancel_btn = QPushButton("Cancel", dialog)
        cancel_btn.clicked.connect(dialog.reject)  # type: ignore[arg-type]
        run_btn = QPushButton("Run", dialog)
        run_btn.clicked.connect(dialog.accept)  # type: ignore[arg-type]
        button_row.addWidget(cancel_btn)
        button_row.addWidget(run_btn)
        layout.addLayout(button_row)
        dialog.setMinimumWidth(420)
        return dialog

    def _show_completion_notice(self, finished_timestamp: str) -> None:
        """Show a completion dialog once maintenance succeeds."""

        dialog = self._build_completion_dialog(finished_timestamp)
        dialog.exec()

    def _build_completion_dialog(self, finished_timestamp: str) -> QDialog:
        """Return the dialog instance used to announce maintenance completion."""

        message = "VACUUM/ANALYZE completed successfully."
        if ChromeDialog is None:
            box = QMessageBox(self)
            box.setIcon(QMessageBox.Icon.Information)
            box.setWindowTitle("Maintenance complete")
            box.setText(message)
            box.setInformativeText(f"Completed at {finished_timestamp}.")
            box.setStandardButtons(QMessageBox.StandardButton.Ok)
            box.setDefaultButton(QMessageBox.StandardButton.Ok)
            return box
        dialog = ChromeDialog(self, title="Maintenance complete")
        layout = dialog.content_layout()
        summary = QLabel(message, dialog)
        summary.setWordWrap(True)
        layout.addWidget(summary)
        ts_label = QLabel(f"Completed at {finished_timestamp}.", dialog)
        ts_label.setObjectName("dbMaintenanceCompletedAt")
        ts_label.setWordWrap(True)
        layout.addWidget(ts_label)
        button_row = QHBoxLayout()
        button_row.setContentsMargins(0, 0, 0, 0)
        button_row.setSpacing(8)
        button_row.addStretch(1)
        close_btn = QPushButton("Close", dialog)
        close_btn.clicked.connect(dialog.accept)  # type: ignore[arg-type]
        button_row.addWidget(close_btn)
        layout.addLayout(button_row)
        dialog.setMinimumWidth(360)
        return dialog

    def _show_error_dialog(self, message: str) -> None:
        """Display a ChromeDialog error message when maintenance fails."""

        if ChromeDialog is None:
            QMessageBox.critical(self, "Maintenance failed", message)
            return
        dialog = ChromeDialog(self, title="Maintenance failed")
        layout = dialog.content_layout()
        label = QLabel(message, dialog)
        label.setWordWrap(True)
        layout.addWidget(label)
        button_row = QHBoxLayout()
        button_row.setContentsMargins(0, 0, 0, 0)
        button_row.setSpacing(8)
        button_row.addStretch(1)
        close_btn = QPushButton("Close", dialog)
        close_btn.clicked.connect(dialog.accept)  # type: ignore[arg-type]
        button_row.addWidget(close_btn)
        layout.addLayout(button_row)
        dialog.setMinimumWidth(360)
        dialog.exec()
