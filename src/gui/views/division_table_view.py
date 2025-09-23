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
from gui.components.empty_state import EmptyStateWidget
from gui.components.skeleton_loader import SkeletonLoaderWidget

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
        self.title_label.setObjectName("viewTitleLabel")
        # Typography will be provided by global QSS / theme; attempt role font if available
        try:  # pragma: no cover - optional enhancement
            from gui.design.typography_roles import TypographyRole, font_for_role

            self.title_label.setFont(font_for_role(TypographyRole.TITLE))
        except Exception:
            pass
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
        # Skeleton loader (shown while async load in future; manual control for now)
        self.skeleton = SkeletonLoaderWidget("table-row", rows=4)
        self.skeleton.start()
        root.addWidget(self.skeleton)
        self.empty_state = EmptyStateWidget("no_division_rows")
        self.empty_state.setObjectName("divisionEmptyState")
        root.addWidget(self.empty_state)
        root.addStretch(1)

    def set_rows(self, rows: List[DivisionStandingEntry]):
        self.viewmodel.set_rows(rows)
        normalized = self.viewmodel.rows()
        self._populate(normalized)
        # Show/hide empty state depending on rows
        if rows:
            self.empty_state.hide()
        else:
            self.empty_state.show()
        self._empty_state_active = not bool(rows)
        # Stop skeleton once rows provided (even if empty -> show empty state)
        self.skeleton.stop()

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
        for r, nr in enumerate(display_rows):
            e = nr.entry
            self.table.setItem(r, 0, QTableWidgetItem(str(e.position)))
            self.table.setItem(r, 1, QTableWidgetItem(e.team_name))
            self.table.setItem(r, 2, QTableWidgetItem(str(e.matches_played)))
            self.table.setItem(r, 3, QTableWidgetItem(str(e.wins)))
            self.table.setItem(r, 4, QTableWidgetItem(str(e.draws)))
            self.table.setItem(r, 5, QTableWidgetItem(str(e.losses)))
            self.table.setItem(r, 6, QTableWidgetItem(nr.differential_text or ""))
            self.table.setItem(r, 7, QTableWidgetItem(str(e.points)))
            self.table.setItem(r, 8, QTableWidgetItem(nr.form or ""))

    def _on_header_clicked(self, logical_index: int):  # pragma: no cover - UI callback
        # Simple toggle single-column sort for now; shift-click multi-column support
        modifiers = QApplication.keyboardModifiers()
        shift = modifiers & Qt.KeyboardModifier.ShiftModifier
        existing = next(
            (i for i, (c, _) in enumerate(self._sort_priority) if c == logical_index), None
        )
        if not shift:
            # Replace priority with this column ascending (or toggle if already first)
            if existing == 0:
                col, asc = self._sort_priority[0]
                self._sort_priority[0] = (col, not asc)
            else:
                self._sort_priority = [(logical_index, True)]
        else:
            if existing is None:
                self._sort_priority.append((logical_index, True))
            else:
                col, asc = self._sort_priority[existing]
                self._sort_priority[existing] = (col, not asc)
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

    # Testing helper -------------------------------------------------
    def is_empty_state_active(self) -> bool:  # pragma: no cover - trivial accessor
        return getattr(self, "_empty_state_active", False)
