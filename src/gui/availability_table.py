"""Custom table widget for player availability editing."""

from __future__ import annotations
from PyQt6.QtWidgets import QTableWidget, QTableWidgetItem, QComboBox
from PyQt6.QtCore import Qt
from typing import List, Dict
from gui.models import PlayerEntry, MatchDate

STATUS_VALUES = ["available", "maybe", "unavailable"]


class AvailabilityTable(QTableWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.players: List[PlayerEntry] = []
        self.match_dates: List[MatchDate] = []
        self.status_map: Dict[str, Dict[str, str]] = {}
        self.setColumnCount(1)
        self.setHorizontalHeaderLabels(["Player"])
        self.verticalHeader().setVisible(False)
        self.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)

    def load(self, players: List[PlayerEntry], match_dates: List[MatchDate]):
        self.clear()
        self.players = players
        self.match_dates = match_dates
        columns = 1 + len(match_dates)
        self.setColumnCount(columns)
        headers = ["Player"] + [d.display for d in match_dates]
        self.setHorizontalHeaderLabels(headers)
        self.setRowCount(len(players))
        for r, p in enumerate(players):
            item = QTableWidgetItem(p.name)
            self.setItem(r, 0, item)
            for c, md in enumerate(match_dates, start=1):
                combo = QComboBox()
                combo.addItems(STATUS_VALUES)
                combo.currentIndexChanged.connect(
                    lambda _i, row=r, iso=md.iso_date: self._on_status_changed(row, iso)
                )
                self.setCellWidget(r, c, combo)
        self.resizeColumnsToContents()

    def _on_status_changed(self, row: int, iso_date: str):
        if row >= len(self.players):
            return
        player = self.players[row]
        combo = self.cellWidget(row, self._date_col_index(iso_date))
        if isinstance(combo, QComboBox):
            status = combo.currentText()
            self.status_map.setdefault(player.name, {})[iso_date] = status

    def _date_col_index(self, iso: str) -> int:
        for idx, md in enumerate(self.match_dates, start=1):
            if md.iso_date == iso:
                return idx
        return -1

    def export_status(self) -> Dict[str, Dict[str, str]]:
        return self.status_map
