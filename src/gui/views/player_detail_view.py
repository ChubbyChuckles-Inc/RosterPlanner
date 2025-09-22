"""PlayerDetailView (Milestone 5.2 scaffold).

Displays a player's historical performance entries (placeholder) and
summary metrics computed by PlayerDetailViewModel.
"""

from __future__ import annotations
from typing import Optional, List
from PyQt6.QtWidgets import (
    QWidget,
    QVBoxLayout,
    QLabel,
    QTableWidget,
    QTableWidgetItem,
    QGroupBox,
)

from gui.models import PlayerEntry, PlayerHistoryEntry
from gui.viewmodels.player_detail_viewmodel import PlayerDetailViewModel


class PlayerDetailView(QWidget):
    def __init__(self, player: PlayerEntry, parent: Optional[QWidget] = None):
        super().__init__(parent)
        self.player = player
        self.viewmodel = PlayerDetailViewModel(player)
        self._build_ui()

    def _build_ui(self):
        root = QVBoxLayout(self)
        self.title_label = QLabel(f"Player: {self.player.name}")
        self.title_label.setStyleSheet("font-weight:600;font-size:14px;")
        root.addWidget(self.title_label)

        hist_box = QGroupBox("History")
        hist_layout = QVBoxLayout(hist_box)
        self.history_table = QTableWidget(0, 2)
        self.history_table.setHorizontalHeaderLabels(["Date", "LivePZ Δ"])  # delta symbol
        self.history_table.horizontalHeader().setStretchLastSection(True)
        hist_layout.addWidget(self.history_table)
        root.addWidget(hist_box)

        self.summary_label = QLabel("No history data")
        root.addWidget(self.summary_label)
        root.addStretch(1)

    def set_history(self, entries: List[PlayerHistoryEntry]):
        self.viewmodel.set_history(entries)
        self._populate_history(entries)
        self.summary_label.setText(self.viewmodel.summary.as_text())

    def _populate_history(self, entries: List[PlayerHistoryEntry]):
        self.history_table.setRowCount(len(entries))
        for r, e in enumerate(entries):
            self.history_table.setItem(r, 0, QTableWidgetItem(e.iso_date))
            delta_text = (
                ""
                if e.live_pz_delta is None
                else ("+" if e.live_pz_delta > 0 else "") + str(e.live_pz_delta)
            )
            self.history_table.setItem(r, 1, QTableWidgetItem(delta_text))


__all__ = ["PlayerDetailView"]
