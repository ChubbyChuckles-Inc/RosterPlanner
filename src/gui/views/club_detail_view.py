"""Club Detail View (Milestone 5.4)

Displays an aggregated overview of all teams in the loaded season grouped by
Division and high-level classification (Erwachsene / Jugend). Provides basic
roll‑ups to prepare for future advanced stats (Milestone 6+):
 - Count of teams per division
 - Classification split (Erwachsene vs Jugend)
 - Placeholder averages (e.g., average roster size if bundles provided later)

This widget is intentionally passive: the caller supplies a list of `TeamEntry`
objects via `set_teams`. No database or scraping logic is embedded to keep it
unit test friendly.
"""

from __future__ import annotations
from typing import List, Dict
from PyQt6.QtWidgets import (
    QWidget,
    QVBoxLayout,
    QLabel,
    QTableWidget,
    QTableWidgetItem,
    QGroupBox,
    QHBoxLayout,
)
from PyQt6.QtCore import Qt
from gui.models import TeamEntry
from gui.components.empty_state import EmptyStateWidget


class ClubDetailView(QWidget):
    """Aggregated club overview for a season.

    Public API:
    - set_teams(teams): populate division summary and meta stats
    """

    def __init__(self, parent: QWidget | None = None):
        super().__init__(parent)
        self._teams: List[TeamEntry] = []
        self._build_ui()

    # UI -----------------------------------------------------------------
    def _build_ui(self):
        root = QVBoxLayout(self)
        self.title_label = QLabel("Club Overview")
        self.title_label.setObjectName("viewTitleLabel")
        root.addWidget(self.title_label)
        # Summary / Empty state container
        self.meta_label = QLabel("")
        self.meta_label.setObjectName("clubMetaLabel")
        root.addWidget(self.meta_label)
        self.empty_state = EmptyStateWidget("no_teams")
        self.empty_state.hide()
        root.addWidget(self.empty_state)

        # Division table
        div_box = QGroupBox("Divisions")
        div_layout = QVBoxLayout(div_box)
        self.div_table = QTableWidget(0, 3)
        self.div_table.setHorizontalHeaderLabels(["Division", "Teams", "Type"])  # Type derived
        self.div_table.horizontalHeader().setStretchLastSection(True)
        div_layout.addWidget(self.div_table)
        root.addWidget(div_box)
        root.addStretch(1)

    # Data ---------------------------------------------------------------
    def set_teams(self, teams: List[TeamEntry]):
        self._teams = list(teams)
        self._populate()

    def _populate(self):
        if not self._teams:
            self.meta_label.setText("")
            self.div_table.setRowCount(0)
            self.empty_state.show()
            return
        self.empty_state.hide()
        # Aggregate by division
        by_div: Dict[str, List[TeamEntry]] = {}
        for t in self._teams:
            by_div.setdefault(t.division, []).append(t)
        rows = sorted(by_div.items(), key=lambda x: x[0])
        self.div_table.setRowCount(len(rows))
        erw = jug = 0
        for row, (div, teams) in enumerate(rows):
            # Determine type heuristic
            div_type = "Jugend" if "Jugend" in div else "Erwachsene"
            if div_type == "Jugend":
                jug += len(teams)
            else:
                erw += len(teams)
            self.div_table.setItem(row, 0, QTableWidgetItem(div))
            self.div_table.setItem(row, 1, QTableWidgetItem(str(len(teams))))
            self.div_table.setItem(row, 2, QTableWidgetItem(div_type))
        total = len(self._teams)
        self.meta_label.setText(f"Total Teams: {total} | Erwachsene: {erw} | Jugend: {jug}")

    # Accessors for tests -----------------------------------------------
    def team_count(self) -> int:  # pragma: no cover - trivial
        return len(self._teams)

    def division_row_count(self) -> int:  # pragma: no cover - trivial
        return self.div_table.rowCount()

    # Export integration (Milestone 5.6) ---------------------------------
    def get_export_rows(self):  # pragma: no cover - simple
        headers = ["Division", "Teams", "Type"]
        rows: list[list[str]] = []
        for r in range(self.div_table.rowCount()):
            row_vals: list[str] = []
            for c in range(self.div_table.columnCount()):
                it = self.div_table.item(r, c)
                row_vals.append(it.text() if it else "")
            rows.append(row_vals)
        return headers, rows

    def get_export_payload(self):  # pragma: no cover - simple
        return {
            "team_count": len(self._teams),
            "divisions": [
                {
                    "division": (
                        self.div_table.item(r, 0).text() if self.div_table.item(r, 0) else ""
                    ),
                    "teams": (
                        int(self.div_table.item(r, 1).text()) if self.div_table.item(r, 1) else 0
                    ),
                    "type": self.div_table.item(r, 2).text() if self.div_table.item(r, 2) else "",
                }
                for r in range(self.div_table.rowCount())
            ],
        }


__all__ = ["ClubDetailView"]
