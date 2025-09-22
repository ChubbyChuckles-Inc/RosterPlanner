"""Team Detail View (Milestone 5.1 initial scaffold).

Displays three primary regions:
 - Roster table (players + LivePZ) using a simple QTableWidget for now (future: custom model)
 - Match list (upcoming/past match dates)
 - LivePZ summary (aggregate metrics placeholder)

This first iteration focuses on a lightweight, testable widget with
public methods to set a TeamRosterBundle. A ViewModel will be layered
on in a subsequent step to decouple data mapping.
"""

from __future__ import annotations
from typing import Optional, List
from PyQt6.QtWidgets import (
    QWidget,
    QVBoxLayout,
    QLabel,
    QTableWidget,
    QTableWidgetItem,
    QListWidget,
    QGroupBox,
    QHBoxLayout,
)
from PyQt6.QtCore import Qt

from gui.models import TeamRosterBundle, PlayerEntry, MatchDate


class TeamDetailView(QWidget):
    """Widget showing team roster, matches, and summary metrics.

    The widget is intentionally slim; it does not fetch data itself but
    exposes ``set_bundle`` to accept a ``TeamRosterBundle`` prepared by
    the caller. This keeps the view free of repository logic and easy
    to unit test (populate with synthetic bundle instances).
    """

    def __init__(self, parent: Optional[QWidget] = None):
        super().__init__(parent)
        self._bundle: Optional[TeamRosterBundle] = None
        self._build_ui()

    # UI -----------------------------------------------------------------
    def _build_ui(self):
        root = QVBoxLayout(self)
        self.title_label = QLabel("Team Detail")
        self.title_label.setObjectName("teamTitleLabel")
        self.title_label.setStyleSheet("font-weight: 600; font-size: 14px;")
        root.addWidget(self.title_label)

        # Roster box
        roster_box = QGroupBox("Roster")
        roster_layout = QVBoxLayout(roster_box)
        self.roster_table = QTableWidget(0, 2)
        self.roster_table.setHorizontalHeaderLabels(["Player", "LivePZ"])  # minimal for now
        self.roster_table.horizontalHeader().setStretchLastSection(True)
        roster_layout.addWidget(self.roster_table)
        root.addWidget(roster_box)

        # Matches box
        matches_box = QGroupBox("Matches")
        matches_layout = QVBoxLayout(matches_box)
        self.match_list = QListWidget()
        matches_layout.addWidget(self.match_list)
        root.addWidget(matches_box)

        # Summary box
        summary_box = QGroupBox("LivePZ Summary")
        summary_layout = QHBoxLayout(summary_box)
        self.summary_label = QLabel("No data")
        summary_layout.addWidget(self.summary_label)
        root.addWidget(summary_box)
        root.addStretch(1)

    # Data population -----------------------------------------------------
    def set_bundle(self, bundle: TeamRosterBundle):
        """Assign a roster bundle and populate child widgets.

        Parameters
        ----------
        bundle: TeamRosterBundle
            Parsed roster + matches for a given team.
        """
        self._bundle = bundle
        self.title_label.setText(f"Team: {bundle.team.name}")
        self._populate_roster(bundle.players)
        self._populate_matches(bundle.match_dates)
        self._populate_summary(bundle.players)

    def _populate_roster(self, players: List[PlayerEntry]):
        self.roster_table.setRowCount(len(players))
        for row, p in enumerate(players):
            self.roster_table.setItem(row, 0, QTableWidgetItem(p.name))
            livepz_text = "" if p.live_pz is None else str(p.live_pz)
            self.roster_table.setItem(row, 1, QTableWidgetItem(livepz_text))

    def _populate_matches(self, matches: List[MatchDate]):
        self.match_list.clear()
        for m in matches:
            label = m.display
            if m.time:
                label += f" {m.time}"
            self.match_list.addItem(label)

    def _populate_summary(self, players: List[PlayerEntry]):
        if not players:
            self.summary_label.setText("No players")
            return
        # Compute simple metrics: count and average LivePZ excluding None
        values = [p.live_pz for p in players if p.live_pz is not None]
        if not values:
            self.summary_label.setText(f"{len(players)} players (no LivePZ data)")
            return
        avg = sum(values) / len(values)
        self.summary_label.setText(
            f"{len(players)} players | LivePZ entries: {len(values)} | Avg: {avg:.1f}"
        )

    # Accessors for tests -------------------------------------------------
    def bundle(self) -> Optional[TeamRosterBundle]:  # pragma: no cover - trivial
        return self._bundle


__all__ = ["TeamDetailView"]
