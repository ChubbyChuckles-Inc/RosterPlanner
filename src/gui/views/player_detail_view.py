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
from gui.components.empty_state import EmptyStateWidget
from gui.viewmodels.player_detail_viewmodel import PlayerDetailViewModel


class PlayerDetailView(QWidget):
    def __init__(self, player: PlayerEntry, parent: Optional[QWidget] = None):
        super().__init__(parent)
        self.player = player
        self.viewmodel = PlayerDetailViewModel(player)
        self._empty_state_active = False
        self._build_ui()

    def _build_ui(self):
        root = QVBoxLayout(self)
        self.title_label = QLabel(f"Player: {self.player.name}")
        self.title_label.setObjectName("viewTitleLabel")  # styled via global QSS
        root.addWidget(self.title_label)

        hist_box = QGroupBox("History")
        hist_layout = QVBoxLayout(hist_box)
        self.history_table = QTableWidget(0, 2)
        self.history_table.setHorizontalHeaderLabels(["Date", "LivePZ Δ"])  # delta symbol
        self.history_table.horizontalHeader().setStretchLastSection(True)
        hist_layout.addWidget(self.history_table)
        root.addWidget(hist_box)

        # Empty state widget (replaces plain summary label)
        self.empty_state = EmptyStateWidget("no_history")
        self.empty_state.setObjectName("playerHistoryEmpty")
        root.addWidget(self.empty_state)
        self.empty_state.show()
        root.addStretch(1)

    def set_history(self, entries: List[PlayerHistoryEntry]):
        self.viewmodel.set_history(entries)
        self._populate_history(entries)
        # Toggle empty state visibility: hide when we have history
        if entries:
            self.empty_state.hide()
            self._empty_state_active = False
        else:
            self.empty_state.show()
            self._empty_state_active = True

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

    # Testing helper -------------------------------------------------
    def is_empty_state_active(self) -> bool:  # pragma: no cover - simple accessor
        return self._empty_state_active


__all__ = ["PlayerDetailView"]
