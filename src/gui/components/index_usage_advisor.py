"""Index usage advisor widget (Milestone 7.11.14).

Provides lightweight heuristics over recorded slow queries to surface
potential missing indexes. It replays recorded queries through
``EXPLAIN QUERY PLAN`` and highlights tables scanned without an index.
Results are presented in a table with the affected table name, the
suggested index columns (when detectable), and a truncated query
preview for reference.
"""

from __future__ import annotations

import re
import sqlite3
from typing import Iterable, Optional, Sequence, Tuple

from PyQt6.QtWidgets import (
    QHBoxLayout,
    QLabel,
    QPushButton,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

try:  # pragma: no cover - optional dependency in tests
    from db.query_perf import QueryPerformanceLogger, QueryRecord
except Exception:  # pragma: no cover

    class QueryRecord:  # type: ignore[no-redef]
        sql: str
        params: object
        ms: float
        rowcount: Optional[int]

    class QueryPerformanceLogger:  # type: ignore[no-redef]
        def records(self) -> Sequence[QueryRecord]:  # noqa: D401
            """Return empty records when logger unavailable."""

            return []


try:  # pragma: no cover - theme mixin optional in some environments
    from gui.components.theme_aware import ThemeAwareMixin  # type: ignore
except Exception:  # pragma: no cover

    class ThemeAwareMixin:  # type: ignore
        def apply_theme(self) -> None:  # noqa: D401
            """Theme hook placeholder."""

            return


__all__ = ["IndexUsageAdvisorWidget"]


class IndexUsageAdvisorWidget(QWidget, ThemeAwareMixin):
    """Surface potential missing index recommendations from slow queries."""

    _READ_ONLY_PREFIXES: Tuple[str, ...] = ("SELECT", "WITH", "EXPLAIN")

    def __init__(self, parent: Optional[QWidget] = None) -> None:
        super().__init__(parent)
        self.setObjectName("dbIndexUsageAdvisor")
        self._conn: Optional[sqlite3.Connection] = None
        self._logger: Optional[QueryPerformanceLogger] = None

        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(6)

        header = QLabel("Index usage advisor")
        header.setObjectName("dbIndexAdvisorHeader")
        root.addWidget(header)

        controls = QHBoxLayout()
        controls.setContentsMargins(0, 0, 0, 0)
        controls.setSpacing(6)

        self.refresh_button = QPushButton("Refresh", self)
        self.refresh_button.setObjectName("dbIndexAdvisorRefresh")
        self.refresh_button.clicked.connect(self.refresh)  # type: ignore[arg-type]
        controls.addWidget(self.refresh_button)
        controls.addStretch(1)

        root.addLayout(controls)

        self.table = QTableWidget(self)
        self.table.setObjectName("dbIndexAdvisorTable")
        self.table.setColumnCount(4)
        self.table.setHorizontalHeaderLabels(
            [
                "Table",
                "Suggested columns",
                "Plan detail",
                "Query",
            ]
        )
        self.table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        self.table.setAlternatingRowColors(True)
        self.table.verticalHeader().setVisible(False)
        self.table.horizontalHeader().setStretchLastSection(True)
        root.addWidget(self.table, 1)

        self.status_label = QLabel("No analysis run yet.", self)
        self.status_label.setObjectName("dbIndexAdvisorStatus")
        self.status_label.setWordWrap(True)
        root.addWidget(self.status_label)

        self._update_enabled_state()

    # ------------------------------------------------------------------
    def set_context(
        self,
        conn: Optional[sqlite3.Connection],
        logger: Optional[QueryPerformanceLogger],
    ) -> None:
        """Assign analysis context consisting of the connection and logger."""

        self._conn = conn
        self._logger = logger
        self._update_enabled_state()
        self.refresh()

    def refresh(self) -> None:
        """Rebuild the recommendation table using the latest slow query data."""

        if not self._conn or not self._logger:
            self._show_unavailable()
            return
        recommendations = self._gather_recommendations()
        self._render_recommendations(recommendations)

    # ------------------------------------------------------------------
    def _update_enabled_state(self) -> None:
        has_inputs = self._conn is not None and self._logger is not None
        self.refresh_button.setEnabled(has_inputs)
        if not has_inputs:
            self.table.setRowCount(0)
            self.status_label.setText(
                "Index advisor unavailable. Provide a connection and slow query logger."
            )

    def _show_unavailable(self) -> None:
        self.table.setRowCount(0)
        self.status_label.setText(
            "Index advisor unavailable. Configure performance logging to enable recommendations."
        )

    # ------------------------------------------------------------------
    def _gather_recommendations(self) -> list[tuple[str, str, str, str]]:
        assert self._conn is not None
        assert self._logger is not None
        conn = self._conn
        seen: set[tuple[str, str]] = set()
        suggestions: list[tuple[str, str, str, str]] = []
        for record in reversed(self._logger.records()):
            sql = (record.sql or "").strip()
            if not sql:
                continue
            if not self._is_read_only(sql):
                continue
            plan_rows = self._explain_query(conn, sql)
            if not plan_rows:
                continue
            tables = self._tables_with_full_scan(plan_rows)
            if not tables:
                continue
            suggested_columns = self._infer_filter_columns(sql)
            query_preview = self._truncate(sql)
            for table_name, detail in tables:
                key = (table_name, query_preview)
                if key in seen:
                    continue
                seen.add(key)
                suggestions.append(
                    (
                        table_name,
                        (
                            ", ".join(suggested_columns)
                            if suggested_columns
                            else "(review WHERE clause)"
                        ),
                        detail,
                        query_preview,
                    )
                )
        return suggestions

    def _render_recommendations(self, rows: Iterable[tuple[str, str, str, str]]) -> None:
        rows = list(rows)
        self.table.setRowCount(len(rows))
        for row_idx, (table_name, columns, detail, preview) in enumerate(rows):
            self.table.setItem(row_idx, 0, QTableWidgetItem(table_name))
            self.table.setItem(row_idx, 1, QTableWidgetItem(columns))
            self.table.setItem(row_idx, 2, QTableWidgetItem(detail))
            preview_item = QTableWidgetItem(self._truncate(preview, 200))
            preview_item.setToolTip(preview)
            self.table.setItem(row_idx, 3, preview_item)
        if rows:
            self.status_label.setText(f"Found {len(rows)} potential index recommendation(s).")
        else:
            self.status_label.setText(
                "No obvious missing index patterns detected in recent slow queries."
            )

    # ------------------------------------------------------------------
    @classmethod
    def _is_read_only(cls, sql: str) -> bool:
        leading = cls._first_token(sql)
        return leading in cls._READ_ONLY_PREFIXES

    @staticmethod
    def _first_token(sql: str) -> str:
        for token in re.split(r"\s+", sql.strip()):
            if token:
                return token.upper()
        return ""

    def _explain_query(self, conn: sqlite3.Connection, sql: str) -> list[str]:
        plan_sql = sql if sql.upper().startswith("EXPLAIN") else f"EXPLAIN QUERY PLAN {sql}"
        try:
            cursor = conn.execute(plan_sql)
            rows = cursor.fetchall()
        except sqlite3.OperationalError:
            return []
        except Exception:  # pragma: no cover - defensive guard
            return []
        details: list[str] = []
        for row in rows:
            if len(row) >= 4:
                details.append(str(row[3]))
            elif row:
                details.append(str(row[-1]))
        return details

    @staticmethod
    def _tables_with_full_scan(details: Sequence[str]) -> list[tuple[str, str]]:
        matches: list[tuple[str, str]] = []
        for detail in details:
            upper = detail.upper()
            if "SCAN" in upper and "USING INDEX" not in upper:
                table_match = re.search(r"SCAN (?:TABLE )?([\w\"]+)", detail, re.IGNORECASE)
                table_name = table_match.group(1) if table_match else "(unknown)"
                matches.append((table_name.replace('"', ""), detail))
        return matches

    @staticmethod
    def _infer_filter_columns(sql: str) -> list[str]:
        where_match = re.search(r"WHERE\s+(.+)$", sql, flags=re.IGNORECASE | re.DOTALL)
        if not where_match:
            return []
        clause = where_match.group(1)
        candidates = re.findall(r"([\w\"]+)\s*=\s*\?", clause)
        if not candidates:
            candidates = re.findall(r"([\w\"]+)\s*=\s*['\"]", clause)
        cleaned = [name.replace('"', "") for name in candidates]
        unique: list[str] = []
        for name in cleaned:
            if name not in unique:
                unique.append(name)
        return unique

    @staticmethod
    def _truncate(value: str, max_length: int = 120) -> str:
        value = value.strip()
        if len(value) <= max_length:
            return value
        return value[: max_length - 1] + "…"
