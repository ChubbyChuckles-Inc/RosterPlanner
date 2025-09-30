"""Query plan analyzer widget (Milestone 7.11.12).

Provides an interactive view over SQLite ``EXPLAIN QUERY PLAN`` output. Users can
paste a read-only SQL query, run the analyzer, and inspect the resulting plan as
a hierarchical tree with lightweight cost categorisation. The widget is designed
for the database panel but stays self-contained for reuse/testing.
"""

from __future__ import annotations

import re
import sqlite3
from dataclasses import dataclass
from typing import Dict, List, Optional, Sequence, Tuple

from PyQt6.QtGui import QColor, QBrush
from PyQt6.QtWidgets import (
    QHBoxLayout,
    QLabel,
    QPushButton,
    QPlainTextEdit,
    QTreeWidget,
    QTreeWidgetItem,
    QVBoxLayout,
    QWidget,
)

try:  # pragma: no cover - theme mixin optional in tests
    from gui.components.theme_aware import ThemeAwareMixin  # type: ignore
except Exception:  # pragma: no cover

    class ThemeAwareMixin:  # type: ignore
        """Fallback mixin when theming infrastructure is unavailable."""

        def apply_theme(self) -> None:  # noqa: D401 - compatibility shim
            """No-op fallback."""
            return


__all__ = ["QueryPlanAnalyzerWidget"]


@dataclass(frozen=True)
class _PlanRow:
    """Structured representation of a single ``EXPLAIN QUERY PLAN`` row."""

    select_id: int
    order: int
    from_index: int
    detail: str


class QueryPlanAnalyzerWidget(QWidget, ThemeAwareMixin):
    """Render structured SQLite query plans with simple cost highlighting."""

    _READ_ONLY_PREFIXES: Tuple[str, ...] = ("SELECT", "WITH", "PRAGMA", "EXPLAIN")

    def __init__(self, parent: Optional[QWidget] = None) -> None:
        """Initialise layout, attach signals, and prepare widget state."""

        super().__init__(parent)
        self.setObjectName("dbQueryPlanAnalyzer")
        self._conn: Optional[sqlite3.Connection] = None
        self._default_table: Optional[str] = None

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(6)

        header = QLabel("Query Plan Analyzer")
        header.setObjectName("dbQueryPlanAnalyzerHeader")
        layout.addWidget(header)

        self.sql_edit = QPlainTextEdit(self)
        self.sql_edit.setObjectName("dbQueryPlanAnalyzerEdit")
        self.sql_edit.setPlaceholderText("Enter a SELECT query to analyse the plan")
        self.sql_edit.setTabChangesFocus(True)
        layout.addWidget(self.sql_edit)

        controls = QHBoxLayout()
        controls.setContentsMargins(0, 0, 0, 0)
        controls.setSpacing(6)

        self.analyze_button = QPushButton("Analyse", self)
        self.analyze_button.setObjectName("dbQueryPlanAnalyzeButton")
        self.analyze_button.clicked.connect(self._on_analyze_clicked)  # type: ignore[arg-type]
        controls.addWidget(self.analyze_button)
        controls.addStretch(1)

        layout.addLayout(controls)

        self.plan_tree = QTreeWidget(self)
        self.plan_tree.setObjectName("dbQueryPlanTree")
        self.plan_tree.setColumnCount(3)
        self.plan_tree.setHeaderLabels(["Step", "Detail", "Cost note"])
        self.plan_tree.setAlternatingRowColors(True)
        layout.addWidget(self.plan_tree, 1)

        self.status_label = QLabel("Enter a query and press Analyse.", self)
        self.status_label.setObjectName("dbQueryPlanStatus")
        self.status_label.setWordWrap(True)
        layout.addWidget(self.status_label)

        self._apply_disabled_state()

    # ------------------------------------------------------------------
    def set_connection(self, conn: Optional[sqlite3.Connection]) -> None:
        """Assign the SQLite connection used for plan extraction."""

        self._conn = conn
        self._apply_disabled_state()

    def set_default_table(self, table: Optional[str]) -> None:
        """Seed the SQL editor with a default ``SELECT`` for *table*."""

        self._default_table = table
        if table and not self.sql_edit.toPlainText().strip():
            self.sql_edit.setPlainText(f"SELECT * FROM {table} LIMIT 100;")

    # ------------------------------------------------------------------
    def _apply_disabled_state(self) -> None:
        """Enable or disable controls based on connection availability."""

        has_conn = self._conn is not None
        self.analyze_button.setEnabled(has_conn)
        if has_conn:
            self.status_label.setText("Enter a query and press Analyse.")
        else:
            self.status_label.setText("No database connection available for analysis.")

    def _on_analyze_clicked(self) -> None:
        """Slot for the Analyse button; validates and runs plan capture."""

        self.run_analysis()

    def run_analysis(self) -> None:
        """Execute the current query and populate the plan tree (test hook)."""

        sql = self.sql_edit.toPlainText().strip()
        self.plan_tree.clear()
        if not sql:
            self.status_label.setText("Enter a query before running analysis.")
            return
        if self._conn is None:
            self.status_label.setText("Database connection unavailable.")
            return
        if not self._is_read_only(sql):
            self._show_read_only_warning()
            return
        plan_sql = self._ensure_explain_prefix(sql)
        try:
            rows = self._fetch_plan_rows(plan_sql)
        except sqlite3.OperationalError as exc:
            self._show_error(f"Plan analysis failed: {exc}")
            return
        except Exception as exc:  # pragma: no cover - defensive guard
            self._show_error(f"Unexpected error: {exc}")
            return
        self._render_plan(rows)

    def _fetch_plan_rows(self, plan_sql: str) -> List[_PlanRow]:
        """Run *plan_sql* and convert cursor output into plan rows."""

        assert self._conn is not None
        cursor = self._conn.execute(plan_sql)
        fetched = cursor.fetchall()
        columns = [desc[0].lower() for desc in cursor.description or []]
        index_map: Dict[str, int] = {name: idx for idx, name in enumerate(columns)}
        plan_rows: List[_PlanRow] = []
        for row in fetched:
            select_id = int(row[index_map.get("selectid", 0)])
            order = int(row[index_map.get("order", 0)])
            from_index = int(row[index_map.get("from", 0)])
            detail = str(row[index_map.get("detail", 0)])
            plan_rows.append(
                _PlanRow(select_id=select_id, order=order, from_index=from_index, detail=detail)
            )
        return plan_rows

    def _render_plan(self, rows: Sequence[_PlanRow]) -> None:
        """Populate the tree widget using *rows* and update status."""

        self.plan_tree.clear()
        if not rows:
            self.status_label.setText("No plan steps returned.")
            return
        by_select: Dict[int, List[_PlanRow]] = {}
        for row in rows:
            by_select.setdefault(row.select_id, []).append(row)
        total_steps = 0
        high_cost = 0
        for select_id in sorted(by_select):
            root = QTreeWidgetItem(self.plan_tree, [f"SELECT {select_id}", "", ""])
            root.setExpanded(True)
            stack: List[Tuple[int, QTreeWidgetItem]] = []
            for entry in sorted(by_select[select_id], key=lambda r: r.order):
                while stack and entry.order <= stack[-1][0]:
                    stack.pop()
                parent = stack[-1][1] if stack else root
                cost_note, severity = self._classify_cost(entry.detail)
                item = QTreeWidgetItem(parent, [f"Step {entry.order}", entry.detail, cost_note])
                self._apply_cost_format(item, severity)
                stack.append((entry.order, item))
                total_steps += 1
                if severity == "high":
                    high_cost += 1
        self.plan_tree.expandAll()
        summary = f"Analysed query: {total_steps} step(s)"
        if high_cost:
            summary += f", {high_cost} flagged as high cost"
        self.status_label.setText(summary)

    @classmethod
    def _classify_cost(cls, detail: str) -> Tuple[str, str]:
        """Return a (note, severity) tuple based on *detail* heuristics."""

        upper = detail.upper()
        if "SCAN" in upper and "USING" not in upper:
            return ("High (full scan)", "high")
        if "SEARCH" in upper and "USING INDEX" in upper:
            return ("Low (indexed search)", "low")
        if "SEARCH" in upper:
            return ("Medium (search)", "medium")
        if "USE TEMP" in upper or "EXECUTE" in upper or "SUBQUERY" in upper:
            return ("Medium (temp/subquery)", "medium")
        return ("Info", "info")

    def _apply_cost_format(self, item: QTreeWidgetItem, severity: str) -> None:
        """Colour code *item* according to *severity*."""

        palette = {
            "high": QColor("#d9534f"),
            "medium": QColor("#f0ad4e"),
            "low": QColor("#5cb85c"),
            "info": None,
        }
        color = palette.get(severity)
        if color is not None:
            brush = QBrush(color)
            for column in range(3):
                item.setForeground(column, brush)

    def _ensure_explain_prefix(self, sql: str) -> str:
        """Ensure *sql* is prefixed with ``EXPLAIN QUERY PLAN`` when absent."""

        if sql.upper().startswith("EXPLAIN"):
            return sql
        return f"EXPLAIN QUERY PLAN {sql}"

    def _is_read_only(self, sql: str) -> bool:
        """Return ``True`` when *sql* begins with an allowed read-only token."""

        leading = self._first_token(sql)
        return leading in self._READ_ONLY_PREFIXES

    @staticmethod
    def _first_token(sql: str) -> str:
        """Extract the first non-empty token from *sql*."""

        for token in re.split(r"\s+", sql.strip()):
            if token:
                return token.upper()
        return ""

    def _show_error(self, message: str) -> None:
        """Report *message* in the status label."""

        self.status_label.setText(message)

    def _show_read_only_warning(self) -> None:
        """Inform the user that mutating statements are not analysed."""

        self.status_label.setText("Only read-only queries can be analysed.")
