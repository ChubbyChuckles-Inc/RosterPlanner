"""Slow query log viewer widget (Milestone 7.11.13).

Renders the captured slow query records produced by ``QueryPerformanceLogger`` in
an interactive table. Users can refresh or clear the buffered records to inspect
recent expensive SQL statements triggered from the GUI.
"""

from __future__ import annotations

import datetime as _dt
from typing import Optional

from PyQt6.QtWidgets import (
    QHBoxLayout,
    QLabel,
    QPushButton,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

try:  # pragma: no cover - optional dependency in certain test environments
    from db.query_perf import QueryPerformanceLogger, QueryRecord
except Exception:  # pragma: no cover

    class QueryPerformanceLogger:  # type: ignore[no-redef]
        """Fallback stub when performance logging is unavailable."""

        def records(self):  # type: ignore[no-untyped-def]
            return []

        def clear(self) -> None:  # type: ignore[no-untyped-def]
            return

    class QueryRecord:  # type: ignore[no-redef]
        sql: str
        params: object
        ms: float
        rowcount: Optional[int]


try:  # pragma: no cover - theme mixin optional in tests
    from gui.components.theme_aware import ThemeAwareMixin  # type: ignore
except Exception:  # pragma: no cover

    class ThemeAwareMixin:  # type: ignore
        """Fallback mixin when theming infrastructure is unavailable."""

        def apply_theme(self) -> None:  # noqa: D401 - compatibility shim
            """No-op fallback."""
            return


__all__ = ["SlowQueryLogViewer"]


class SlowQueryLogViewer(QWidget, ThemeAwareMixin):
    """Display buffered slow query records in a table view."""

    def __init__(self, parent: Optional[QWidget] = None) -> None:
        super().__init__(parent)
        self.setObjectName("dbSlowQueryLogViewer")
        self._logger: Optional[QueryPerformanceLogger] = None
        self._threshold_ms: Optional[float] = None

        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(6)

        header = QLabel("Slow query log")
        header.setObjectName("dbSlowQueryHeader")
        root.addWidget(header)

        controls = QHBoxLayout()
        controls.setContentsMargins(0, 0, 0, 0)
        controls.setSpacing(6)

        self.refresh_button = QPushButton("Refresh", self)
        self.refresh_button.setObjectName("dbSlowQueryRefresh")
        self.refresh_button.clicked.connect(self.refresh)  # type: ignore[arg-type]
        controls.addWidget(self.refresh_button)

        self.clear_button = QPushButton("Clear log", self)
        self.clear_button.setObjectName("dbSlowQueryClear")
        self.clear_button.clicked.connect(self._on_clear_clicked)  # type: ignore[arg-type]
        controls.addWidget(self.clear_button)

        controls.addStretch(1)
        root.addLayout(controls)

        self.table = QTableWidget(self)
        self.table.setObjectName("dbSlowQueryTable")
        self.table.setColumnCount(4)
        self.table.setHorizontalHeaderLabels(
            [
                "Duration (ms)",
                "SQL",
                "Params",
                "Rowcount",
            ]
        )
        self.table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        self.table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        self.table.setAlternatingRowColors(True)
        self.table.verticalHeader().setVisible(False)
        self.table.horizontalHeader().setStretchLastSection(True)
        root.addWidget(self.table, 1)

        self.status_label = QLabel("Slow query logging unavailable.", self)
        self.status_label.setObjectName("dbSlowQueryStatus")
        self.status_label.setWordWrap(True)
        root.addWidget(self.status_label)

        self._update_enabled_state()

    # ------------------------------------------------------------------
    def set_logger(
        self,
        logger: Optional[QueryPerformanceLogger],
        *,
        threshold_ms: Optional[float] = None,
    ) -> None:
        """Assign the backing ``QueryPerformanceLogger`` instance."""

        self._logger = logger
        self._threshold_ms = threshold_ms
        self._update_enabled_state()
        self.refresh()

    def refresh(self) -> None:
        """Reload the table with the latest slow query records."""

        logger = self._logger
        if logger is None:
            self._show_unavailable()
            return
        records = list(logger.records())
        if not records:
            self.table.setRowCount(0)
            threshold_note = (
                f"threshold: {self._threshold_ms:.1f} ms" if self._threshold_ms is not None else ""
            )
            summary = "No slow queries captured."
            if threshold_note:
                summary += f" ({threshold_note})"
            self.status_label.setText(summary)
            return
        # Show newest first for readability.
        records = list(reversed(records))
        self.table.setRowCount(len(records))
        for row_idx, rec in enumerate(records):
            self.table.setItem(row_idx, 0, QTableWidgetItem(f"{rec.ms:.1f}"))
            sql_item = QTableWidgetItem(self._truncate_text(rec.sql))
            sql_item.setToolTip(rec.sql)
            self.table.setItem(row_idx, 1, sql_item)
            params_text = self._stringify_params(rec.params)
            params_item = QTableWidgetItem(params_text)
            params_item.setToolTip(params_text)
            self.table.setItem(row_idx, 2, params_item)
            rowcount_text = "" if rec.rowcount is None else str(rec.rowcount)
            self.table.setItem(row_idx, 3, QTableWidgetItem(rowcount_text))
        threshold_note = (
            f"threshold: {self._threshold_ms:.1f} ms" if self._threshold_ms is not None else ""
        )
        fetched_at = _dt.datetime.now().strftime("%H:%M:%S")
        summary = f"Showing {len(records)} slow query record(s)" + (
            f" ({threshold_note})" if threshold_note else ""
        )
        self.status_label.setText(f"{summary} — refreshed at {fetched_at}")

    def clear_log(self) -> None:
        """Clear captured records from the logger (if available)."""

        if self._logger is None:
            return
        self._logger.clear()
        self.refresh()

    # ------------------------------------------------------------------
    def _on_clear_clicked(self) -> None:
        self.clear_log()

    def _update_enabled_state(self) -> None:
        has_logger = self._logger is not None
        self.refresh_button.setEnabled(has_logger)
        self.clear_button.setEnabled(has_logger)
        if not has_logger:
            self.table.setRowCount(0)

    def _show_unavailable(self) -> None:
        self.table.setRowCount(0)
        self.status_label.setText(
            "Slow query logging unavailable. Configure query performance instrumentation to collect entries."
        )

    @staticmethod
    def _truncate_text(value: str, *, max_length: int = 160) -> str:
        """Return *value* truncated to ``max_length`` characters with ellipsis."""

        if len(value) <= max_length:
            return value
        return value[: max_length - 1] + "…"

    @staticmethod
    def _stringify_params(params: object) -> str:
        """Return a concise representation of *params* suitable for display."""

        if params is None:
            return ""
        if isinstance(params, (list, tuple)):
            return ", ".join(repr(p) for p in params)
        if isinstance(params, dict):
            return ", ".join(f"{k}={v!r}" for k, v in params.items())
        return repr(params)
