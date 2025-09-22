"""DivisionTableView (Milestone 5.3)

Simple QTableWidget-based view showing division standings. Backed by
`DivisionTableViewModel` which supplies normalized rows.
"""

from __future__ import annotations
from typing import Optional, List, Tuple
from PyQt6.QtWidgets import (
    QWidget,
    QVBoxLayout,
    QLabel,
    QTableWidget,
    QTableWidgetItem,
    QHeaderView,
    QApplication,
)

from gui.viewmodels.division_table_viewmodel import DivisionTableViewModel, NormalizedDivisionRow
from gui.services.multi_column_sort import MultiColumnSorter, SortKey
from PyQt6.QtCore import Qt
from gui.models import DivisionStandingEntry

__all__ = ["DivisionTableView"]


class DivisionTableView(QWidget):
    def __init__(self, parent: Optional[QWidget] = None):
        super().__init__(parent)
        self.viewmodel = DivisionTableViewModel()
        # sort priority: list of (column_index, ascending)
        self._sort_priority: List[Tuple[int, bool]] = []
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
        header = self.table.horizontalHeader()
        header.setSectionResizeMode(QHeaderView.ResizeMode.ResizeToContents)
        header.setStretchLastSection(True)
        header.sectionClicked.connect(self._on_header_clicked)  # type: ignore
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
        # Apply sort priority if any to the viewmodel rows (without mutating original ordering)
        display_rows = rows
        if self._sort_priority:
            # Map column index to value extraction
            index_to_key = {
                0: lambda nr: nr.entry.position,
                1: lambda nr: nr.entry.team_name.lower(),
                2: lambda nr: nr.entry.matches_played,
                3: lambda nr: nr.entry.wins,
                4: lambda nr: nr.entry.draws,
                5: lambda nr: nr.entry.losses,
                6: lambda nr: nr.differential_text or "",  # treat as string
                7: lambda nr: nr.entry.points,
                8: lambda nr: nr.form or "",
            }
            sort_keys = [SortKey(index_to_key[idx], asc) for idx, asc in self._sort_priority]
            display_rows = MultiColumnSorter(display_rows).sort(sort_keys)

        self.table.setRowCount(len(display_rows))
        for r, row in enumerate(display_rows):
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

    # Sorting logic -------------------------------------------------
    def _on_header_clicked(self, logical_index: int):  # pragma: no cover - GUI event
        modifiers = QApplication.keyboardModifiers()  # type: ignore
        shift = bool(modifiers & Qt.KeyboardModifier.ShiftModifier)
        # Determine if column already in priority
        existing = next(
            (i for i, (col, _) in enumerate(self._sort_priority) if col == logical_index), None
        )
        if not shift:
            # Reset priority to this column, toggle ascending if was sole column
            if existing is not None and len(self._sort_priority) == 1:
                col, asc = self._sort_priority[0]
                self._sort_priority = [(col, not asc)]
            else:
                self._sort_priority = [(logical_index, True)]
        else:
            # Shift-click adds or toggles that column while preserving earlier order
            if existing is None:
                self._sort_priority.append((logical_index, True))
            else:
                col, asc = self._sort_priority[existing]
                self._sort_priority[existing] = (col, not asc)
        # Re-populate with new ordering
        self._populate(self.viewmodel.rows())

    def apply_sort_priority(self, priority: List[Tuple[int, bool]]):
        """Programmatic API for tests to set multi-column sort priority.

        Args:
            priority: list of (column_index, ascending)
        """
        self._sort_priority = list(priority)
        self._populate(self.viewmodel.rows())

    # Export integration (Milestone 5.6) ---------------------------------
    def get_export_rows(self) -> tuple[List[str], List[List[str]]]:  # pragma: no cover - simple
        headers = [
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
        data: List[List[str]] = []
        for r in range(self.table.rowCount()):
            row_vals: List[str] = []
            for c in range(self.table.columnCount()):
                item = self.table.item(r, c)
                row_vals.append(item.text() if item else "")
            data.append(row_vals)
        return headers, data

    def get_export_payload(self):  # pragma: no cover - simple
        # Provide richer JSON with typed fields using viewmodel normalized rows
        payload = []
        for nr in self.viewmodel.rows():
            e = nr.entry
            payload.append(
                {
                    "position": e.position,
                    "team_name": e.team_name,
                    "matches_played": e.matches_played,
                    "wins": e.wins,
                    "draws": e.draws,
                    "losses": e.losses,
                    "differential": nr.differential_text,
                    "points": e.points,
                    "form": nr.form,
                }
            )
        return payload
