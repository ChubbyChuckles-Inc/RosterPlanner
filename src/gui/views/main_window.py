"""Dock-based MainWindow (Milestone 2.1).

This is an early refactor of the legacy monolithic main window into a
QMainWindow using a DockManager abstraction. For now only two docks are
implemented mirroring prior functionality:
 - navigation: teams list + calendar + basic actions
 - availability: player availability table
A simple central placeholder widget is provided for future tabbed document
area (Milestone 2.1.1).

The original gui.main_window.MainWindow is kept as a compatibility shim that
re-exports this class to avoid breaking existing imports.
"""

from __future__ import annotations
from typing import List
import os

from PyQt6.QtWidgets import (
    QMainWindow,
    QWidget,
    QVBoxLayout,
    QHBoxLayout,
    QPushButton,
    QLabel,
    QListWidget,
    QListWidgetItem,
    QMessageBox,
    QCalendarWidget,
    QDockWidget,
)
from PyQt6.QtCore import Qt

from gui.views.dock_manager import DockManager
from gui.views.document_area import DocumentArea
from gui.workers import LandingLoadWorker, RosterLoadWorker
from gui.models import TeamEntry, TeamRosterBundle
from gui.availability_table import AvailabilityTable
from planning import availability_store


class MainWindow(QMainWindow):  # Dock-based
    def __init__(self, club_id: int, season: int, data_dir: str):
        super().__init__()
        self.setWindowTitle("Roster Planner (Docked)")
        self.club_id = club_id
        self.season = season
        self.data_dir = data_dir
        self.availability_path = os.path.join(data_dir, availability_store.DEFAULT_FILENAME)
        self.av_state = availability_store.load(self.availability_path)
        self.teams: List[TeamEntry] = []

        self.dock_manager = DockManager()
        self._register_docks()
        self._build_document_area()
        self._create_initial_docks()
        self._load_landing()

    # Registration ---------------------------------------------------
    def _register_docks(self):
        self.dock_manager.register("navigation", "Navigation", self._build_navigation_dock)
        self.dock_manager.register("availability", "Availability", self._build_availability_dock)

    # Central area placeholder ---------------------------------------
    def _build_document_area(self):
        self.document_area = DocumentArea()
        # For now, empty. Future: open a welcome/dashboard tab.
        self.setCentralWidget(self.document_area)

    def _create_initial_docks(self):
        # Create and add docks with default positions
        nav_dock = self.dock_manager.create("navigation")
        self.addDockWidget(Qt.DockWidgetArea.LeftDockWidgetArea, nav_dock)
        avail_dock = self.dock_manager.create("availability")
        self.addDockWidget(Qt.DockWidgetArea.RightDockWidgetArea, avail_dock)

    # Dock factories -------------------------------------------------
    def _build_navigation_dock(self) -> QWidget:
        container = QWidget()
        layout = QVBoxLayout(container)

        button_bar = QHBoxLayout()
        self.refresh_btn = QPushButton("Refresh Teams")
        self.refresh_btn.clicked.connect(self._load_landing)
        self.load_roster_btn = QPushButton("Load Roster")
        self.load_roster_btn.clicked.connect(self._load_selected_roster)
        self.save_btn = QPushButton("Save Availability")
        self.save_btn.clicked.connect(self._save_availability)
        button_bar.addWidget(self.refresh_btn)
        button_bar.addWidget(self.load_roster_btn)
        button_bar.addWidget(self.save_btn)
        layout.addLayout(button_bar)

        layout.addWidget(QLabel("Teams"))
        self.team_list = QListWidget()
        layout.addWidget(self.team_list)

        layout.addWidget(QLabel("Match Dates (Calendar)"))
        self.calendar = QCalendarWidget()
        self.calendar.setGridVisible(True)
        layout.addWidget(self.calendar)

        self.status_label = QLabel("Ready")
        layout.addWidget(self.status_label)
        return container

    def _build_availability_dock(self) -> QWidget:
        container = QWidget()
        layout = QVBoxLayout(container)
        layout.addWidget(QLabel("Player Availability"))
        self.table = AvailabilityTable()
        layout.addWidget(self.table)
        return container

    # Status helper --------------------------------------------------
    def _set_status(self, text: str):
        if hasattr(self, "status_label"):
            self.status_label.setText(text)

    # Landing + Teams ------------------------------------------------
    def _load_landing(self):
        self._set_status("Loading teams...")
        if hasattr(self, "refresh_btn"):
            self.refresh_btn.setEnabled(False)
        self.worker = LandingLoadWorker(self.club_id, self.season)
        self.worker.finished.connect(self._on_landing_loaded)
        self.worker.start()

    def _on_landing_loaded(self, teams: List[TeamEntry], error: str):
        if hasattr(self, "refresh_btn"):
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

    # Roster + Players -----------------------------------------------
    def _load_selected_roster(self):
        item = (
            getattr(self, "team_list", None).currentItem() if hasattr(self, "team_list") else None
        )
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
            # Automatically open / focus a team detail tab placeholder
            self.open_team_detail(bundle.team)
        self.table.load(bundle.players, bundle.match_dates)
        team_id = bundle.team.team_id
        if team_id in self.av_state.teams:
            team_av = self.av_state.teams[team_id]
            # Future: apply saved statuses to the UI components
            _ = team_av  # placeholder usage
        self.av_state.ensure_team(team_id, [p.name for p in bundle.players])

    # Persistence ----------------------------------------------------
    def _save_availability(self):
        selected_item = self.team_list.currentItem() if hasattr(self, "team_list") else None
        team: TeamEntry | None = None
        if selected_item:
            team = selected_item.data(Qt.ItemDataRole.UserRole)
        for player, date_map in self.table.export_status().items():
            for date_iso, status in date_map.items():
                if team:
                    self.av_state.set_player_status(team.team_id, date_iso, player, status)
        availability_store.save(self.av_state, self.availability_path)
        self._set_status("Availability saved")
        QMessageBox.information(self, "Saved", "Availability data saved.")

    # Team Detail Tabs ----------------------------------------------
    def open_team_detail(self, team: TeamEntry):
        doc_id = f"team:{team.team_id}"
        if not hasattr(self, "document_area"):
            return

        def factory():
            w = QWidget()
            lay = QVBoxLayout(w)
            lay.addWidget(QLabel(f"Team Detail: {team.name}"))
            lay.addWidget(QLabel(f"Division: {team.division}"))
            lay.addWidget(QLabel("(Detailed view forthcoming)"))
            return w

        self.document_area.open_or_focus(doc_id, team.name, factory)


__all__ = ["MainWindow"]
