"""Main window implementation for roster planning GUI."""

from __future__ import annotations
from PyQt6.QtWidgets import (
    QMainWindow,
    QWidget,
    QVBoxLayout,
    QHBoxLayout,
    QPushButton,
    QLabel,
    QListWidget,
    QListWidgetItem,
    QFileDialog,
    QMessageBox,
    QSplitter,
    QCalendarWidget,
    QSizePolicy,
)
from PyQt6.QtCore import Qt
from typing import List
from gui.workers import LandingLoadWorker, RosterLoadWorker
from gui.models import TeamEntry, TeamRosterBundle
from gui.availability_table import AvailabilityTable
from planning import availability_store
import os


class MainWindow(QMainWindow):
    def __init__(self, club_id: int, season: int, data_dir: str):
        super().__init__()
        self.setWindowTitle("Roster Planner")
        self.club_id = club_id
        self.season = season
        self.data_dir = data_dir
        self.availability_path = os.path.join(data_dir, availability_store.DEFAULT_FILENAME)
        self.av_state = availability_store.load(self.availability_path)
        self.teams: List[TeamEntry] = []

        self._build_ui()
        self._load_landing()

    def _build_ui(self):
        central = QWidget()
        self.setCentralWidget(central)
        layout = QVBoxLayout(central)

        top_bar = QHBoxLayout()
        self.refresh_btn = QPushButton("Refresh Teams")
        self.refresh_btn.clicked.connect(self._load_landing)
        self.load_roster_btn = QPushButton("Load Roster")
        self.load_roster_btn.clicked.connect(self._load_selected_roster)
        self.save_btn = QPushButton("Save Availability")
        self.save_btn.clicked.connect(self._save_availability)
        top_bar.addWidget(self.refresh_btn)
        top_bar.addWidget(self.load_roster_btn)
        top_bar.addWidget(self.save_btn)
        top_bar.addStretch(1)
        layout.addLayout(top_bar)

        splitter = QSplitter()
        left_panel = QWidget()
        left_layout = QVBoxLayout(left_panel)
        left_layout.addWidget(QLabel("Teams"))
        self.team_list = QListWidget()
        left_layout.addWidget(self.team_list)
        left_layout.addWidget(QLabel("Match Dates (Calendar)"))
        self.calendar = QCalendarWidget()
        self.calendar.setGridVisible(True)
        left_layout.addWidget(self.calendar)
        splitter.addWidget(left_panel)

        right_panel = QWidget()
        right_layout = QVBoxLayout(right_panel)
        right_layout.addWidget(QLabel("Player Availability"))
        self.table = AvailabilityTable()
        right_layout.addWidget(self.table)
        splitter.addWidget(right_panel)

        splitter.setStretchFactor(0, 1)
        splitter.setStretchFactor(1, 3)
        layout.addWidget(splitter)

        self.status_label = QLabel("Ready")
        layout.addWidget(self.status_label)

    def _set_status(self, text: str):
        self.status_label.setText(text)

    # Landing + Teams
    def _load_landing(self):
        self._set_status("Loading teams...")
        self.refresh_btn.setEnabled(False)
        self.worker = LandingLoadWorker(self.club_id, self.season)
        self.worker.finished.connect(self._on_landing_loaded)
        self.worker.start()

    def _on_landing_loaded(self, teams: List[TeamEntry], error: str):
        self.refresh_btn.setEnabled(True)
        if error:
            QMessageBox.critical(self, "Error", error)
            self._set_status("Failed to load teams")
            return
        self.teams = teams
        self.team_list.clear()
        for t in teams:
            item = QListWidgetItem(f"{t.division} - {t.name}")
            item.setData(Qt.ItemDataRole.UserRole, t)
            self.team_list.addItem(item)
        self._set_status(f"Loaded {len(teams)} teams")

    # Roster + Players
    def _load_selected_roster(self):
        item = self.team_list.currentItem()
        if not item:
            return
        team: TeamEntry = item.data(Qt.ItemDataRole.UserRole)
        self._set_status(f"Loading roster for {team.name}...")
        self.roster_worker = RosterLoadWorker(team, self.season)
        self.roster_worker.finished.connect(self._on_roster_loaded)
        self.roster_worker.start()

    def _on_roster_loaded(self, bundle: TeamRosterBundle, error: str):
        if error:
            QMessageBox.warning(self, "Roster Load", error)
            self._set_status("Roster load issue")
        else:
            self._set_status(f"Roster loaded: {bundle.team.name} ({len(bundle.players)} players)")
        self.table.load(bundle.players, bundle.match_dates)
        # Integrate stored availability if exists
        team_id = bundle.team.team_id
        if team_id in self.av_state.teams:
            team_av = self.av_state.teams[team_id]
            # Not applying statuses to combos yet (future enhancement)
            pass
        # Ensure team/players present in availability state
        self.av_state.ensure_team(team_id, [p.name for p in bundle.players])

    # Persistence
    def _save_availability(self):
        # Merge table status into state
        for player, date_map in self.table.export_status().items():
            for date_iso, status in date_map.items():
                # Find selected team id
                item = self.team_list.currentItem()
                if not item:
                    continue
                team: TeamEntry = item.data(Qt.ItemDataRole.UserRole)
                self.av_state.set_player_status(team.team_id, date_iso, player, status)
        availability_store.save(self.av_state, self.availability_path)
        self._set_status("Availability saved")
        QMessageBox.information(self, "Saved", "Availability data saved.")
