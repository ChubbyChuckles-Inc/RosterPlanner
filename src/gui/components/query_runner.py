"""Ad-hoc read-only query runner widget (Milestone 7.11.11).

This widget lets power users execute SELECT-style SQL against the
currently loaded SQLite database. It enforces a read-only policy by
rejecting statements that do not begin with ``SELECT``, ``WITH``,
``EXPLAIN`` or ``PRAGMA``. Results are rendered in a table view and the
user can optionally prepend ``EXPLAIN QUERY PLAN`` to inspect execution
plans. The widget is intentionally self-contained so the Database panel
can host it without additional plumbing.
"""

from __future__ import annotations

import re
import sqlite3
import time
from typing import Iterable, Optional, Sequence

from PyQt6.QtCore import Qt, pyqtSignal
from PyQt6.QtGui import QColor, QFont, QSyntaxHighlighter, QTextCharFormat, QTextDocument
from PyQt6.QtWidgets import (
    QCheckBox,
    QHBoxLayout,
    QLabel,
    QMessageBox,
    QPushButton,
    QPlainTextEdit,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

try:  # pragma: no cover - fallback for isolated tests
    from gui.components.theme_aware import ThemeAwareMixin  # type: ignore
except Exception:  # pragma: no cover

    class ThemeAwareMixin:  # type: ignore
        """Fallback mixin when theming infrastructure is unavailable."""

        def apply_theme(self) -> None:  # noqa: D401
            """No-op theme hook."""


__all__ = ["QueryRunnerWidget"]

_SQL_KEYWORDS: Sequence[str] = (
    "SELECT",
    "FROM",
    "WHERE",
    "GROUP",
    "BY",
    "ORDER",
    "LIMIT",
    "OFFSET",
    "JOIN",
    "ON",
    "UNION",
    "WITH",
    "EXPLAIN",
    "QUERY",
    "PLAN",
    "PRAGMA",
)

_READ_ONLY_PREFIXES: tuple[str, ...] = ("SELECT", "WITH", "PRAGMA", "EXPLAIN")


class _SqlHighlighter(QSyntaxHighlighter):
    """Very small SQL syntax highlighter for the query edit."""

    def __init__(self, document: QTextDocument) -> None:
        super().__init__(document)
        keyword_format = QTextCharFormat()
        keyword_format.setForeground(QColor("#6C9AFF"))
        keyword_format.setFontWeight(QFont.Weight.Bold)
        self._keyword_rules = [
            (re.compile(rf"\\b{kw}\\b", re.IGNORECASE), keyword_format) for kw in _SQL_KEYWORDS
        ]

    def highlightBlock(self, text: str) -> None:  # noqa: N802 - Qt API naming
        for pattern, fmt in self._keyword_rules:
            for match in pattern.finditer(text):
                start, end = match.span()
                self.setFormat(start, end - start, fmt)


class QueryRunnerWidget(QWidget, ThemeAwareMixin):
    """Execute read-only SQL queries and render the result set."""

    queryExecuted = pyqtSignal()

    def __init__(self, parent: Optional[QWidget] = None) -> None:
        """Construct the widget and wire up child controls."""

        super().__init__(parent)
        self.setObjectName("dbQueryRunner")
        self._conn: Optional[sqlite3.Connection] = None
        self._default_table: Optional[str] = None

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(6)

        header = QLabel("Ad-hoc Query Runner")
        header.setObjectName("dbQueryRunnerHeader")
        layout.addWidget(header)

        self.sql_edit = QPlainTextEdit(self)
        self.sql_edit.setObjectName("dbQueryRunnerEdit")
        self.sql_edit.setPlaceholderText("Enter a SELECT query (read-only)")
        self.sql_edit.setTabChangesFocus(True)
        _SqlHighlighter(self.sql_edit.document())
        layout.addWidget(self.sql_edit)

        controls = QHBoxLayout()
        controls.setContentsMargins(0, 0, 0, 0)
        controls.setSpacing(6)

        self.run_button = QPushButton("Run", self)
        self.run_button.setObjectName("dbQueryRunnerRunButton")
        self.run_button.clicked.connect(self._on_run_clicked)  # type: ignore
        controls.addWidget(self.run_button)

        self.explain_toggle = QCheckBox("Show EXPLAIN plan", self)
        self.explain_toggle.setObjectName("dbQueryRunnerExplainToggle")
        controls.addWidget(self.explain_toggle)
        controls.addStretch(1)

        layout.addLayout(controls)

        self.result_table = QTableWidget(self)
        self.result_table.setObjectName("dbQueryRunnerTable")
        self.result_table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        self.result_table.setAlternatingRowColors(True)
        layout.addWidget(self.result_table, 1)

        self.status_label = QLabel("Enter a query and press Run.", self)
        self.status_label.setObjectName("dbQueryRunnerStatus")
        self.status_label.setWordWrap(True)
        layout.addWidget(self.status_label)

    # ------------------------------------------------------------------
    def set_connection(self, conn: Optional[sqlite3.Connection]) -> None:
        """Assign the SQLite connection used for query execution."""

        self._conn = conn
        if conn is None:
            self.status_label.setText("No database connection available.")
            self.run_button.setEnabled(False)
        else:
            self.status_label.setText("Enter a query and press Run.")
            self.run_button.setEnabled(True)

    def set_default_table(self, table: Optional[str]) -> None:
        """Update the default table used to prefill helper queries."""

        self._default_table = table
        if table and not self.sql_edit.toPlainText().strip():
            self.sql_edit.setPlainText(f"SELECT * FROM {table} LIMIT 100;")

    # ------------------------------------------------------------------
    def _on_run_clicked(self) -> None:
        """Validate the current SQL text and trigger execution."""

        sql = self.sql_edit.toPlainText().strip()
        if not sql:
            self.status_label.setText("Enter a query before running.")
            return
        if not self._conn:
            self.status_label.setText("Database connection unavailable.")
            return
        if not self._is_read_only(sql):
            self._show_read_only_warning(sql)
            return
        execute_sql = self._wrap_with_explain(sql) if self.explain_toggle.isChecked() else sql
        self._execute_query(execute_sql)

    def _is_read_only(self, sql: str) -> bool:
        """Return True if *sql* starts with an allowed read-only verb."""

        leading = self._first_token(sql)
        return leading in _READ_ONLY_PREFIXES or sql.upper().startswith("EXPLAIN QUERY PLAN")

    @staticmethod
    def _first_token(sql: str) -> str:
        """Extract the first word token from the SQL string."""

        for token in re.split(r"\s+", sql.strip()):
            if token:
                return token.upper()
        return ""

    def _wrap_with_explain(self, sql: str) -> str:
        """Prefix *sql* with EXPLAIN QUERY PLAN when needed."""

        if sql.upper().startswith("EXPLAIN"):
            return sql
        return f"EXPLAIN QUERY PLAN {sql}"

    def _execute_query(self, sql: str) -> None:
        """Run *sql* against the active connection and populate results."""

        assert self._conn is not None
        start = time.perf_counter()
        should_emit = False
        try:
            cursor = self._conn.execute(sql)
            rows = cursor.fetchall()
            columns = [desc[0] for desc in cursor.description or []]
            duration_ms = (time.perf_counter() - start) * 1000.0
            self._populate_table(columns, rows)
            self.status_label.setText(f"Query returned {len(rows)} row(s) in {duration_ms:.1f} ms.")
            should_emit = True
        except sqlite3.OperationalError as exc:
            self._show_error(f"Query failed: {exc}")
            should_emit = True
        except Exception as exc:  # pragma: no cover - defensive guard
            self._show_error(f"Unexpected error: {exc}")
            should_emit = True
        finally:
            if should_emit:
                self.queryExecuted.emit()

    def _populate_table(self, columns: Iterable[str], rows: Sequence[Sequence[object]]) -> None:
        """Render *rows* with the provided *columns* into the table widget."""

        self.result_table.clear()
        cols = list(columns)
        self.result_table.setColumnCount(len(cols))
        self.result_table.setHorizontalHeaderLabels(cols)
        self.result_table.setRowCount(len(rows))
        for row_idx, row in enumerate(rows):
            for col_idx, value in enumerate(row):
                item = QTableWidgetItem(self._stringify(value))
                item.setFlags(Qt.ItemFlag.ItemIsSelectable | Qt.ItemFlag.ItemIsEnabled)
                self.result_table.setItem(row_idx, col_idx, item)
        self.result_table.resizeColumnsToContents()

    @staticmethod
    def _stringify(value: object) -> str:
        """Convert *value* into a concise display string."""

        if value is None:
            return "NULL"
        text = str(value)
        if len(text) > 500:
            text = text[:497] + "..."
        return text

    def _show_error(self, message: str) -> None:
        """Display *message* and optionally show a warning dialog."""

        self.status_label.setText(message)
        if self.isVisible():  # pragma: no cover - dialogs hard to test
            QMessageBox.warning(self, "Query Runner", message)

    def _show_read_only_warning(self, sql: str) -> None:
        """Inform the user that mutation queries are not allowed."""

        self.status_label.setText("Only read-only queries are permitted.")
        if self.isVisible():  # pragma: no cover
            QMessageBox.information(
                self,
                "Read-only mode",
                "The Database panel only permits SELECT/PRAGMA queries.",
            )

    # Exposed for tests -------------------------------------------------
    def run_query(self) -> None:
        """Execute the current query programmatically (testing hook)."""

        self._on_run_clicked()
