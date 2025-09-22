"""DivisionTableView (Milestone 5.3)

Simple QTableWidget-based view showing division standings. Backed by
`DivisionTableViewModel` which supplies normalized rows.
"""

from __future__ import annotations
from typing import Optional, List
from PyQt6.QtWidgets import (
    QWidget,
    QVBoxLayout,
    QLabel,
    QTableWidget,
    QTableWidgetItem,
    QHeaderView,
)

from gui.viewmodels.division_table_viewmodel import DivisionTableViewModel, NormalizedDivisionRow
from gui.models import DivisionStandingEntry

__all__ = ["DivisionTableView"]


class DivisionTableView(QWidget):
    def __init__(self, parent: Optional[QWidget] = None):
        super().__init__(parent)
        self.viewmodel = DivisionTableViewModel()
        self._build_ui()

    def _build_ui(self):
        root = QVBoxLayout(self)
        self.title_label = QLabel("Division Table")
        self.title_label.setStyleSheet("font-weight:600;font-size:14px;")
        root.addWidget(self.title_label)
        self.table = QTableWidget(0, 9)
        self.table.setHorizontalHeaderLabels(
            [
                "Pos",
                "Team",
                "MP",
                "W",
                "D",
                "L",
                "+/-",
                "Pts",
                "Form",
            ]
        )
        self.table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.ResizeToContents)
        self.table.horizontalHeader().setStretchLastSection(True)
        root.addWidget(self.table)
        self.summary_label = QLabel("No teams")
        root.addWidget(self.summary_label)
        root.addStretch(1)

    def set_rows(self, rows: List[DivisionStandingEntry]):
        self.viewmodel.set_rows(rows)
        normalized = self.viewmodel.rows()
        self._populate(normalized)
        self.summary_label.setText(self.viewmodel.summary.as_text())

    def _populate(self, rows: List[NormalizedDivisionRow]):
        self.table.setRowCount(len(rows))
        for r, row in enumerate(rows):
            e = row.entry
            cells = [
                str(e.position),
                e.team_name,
                str(e.matches_played),
                str(e.wins),
                str(e.draws),
                str(e.losses),
                row.differential_text or "",
                str(e.points),
                row.form or "",
            ]
            for c, text in enumerate(cells):
                self.table.setItem(r, c, QTableWidgetItem(text))
