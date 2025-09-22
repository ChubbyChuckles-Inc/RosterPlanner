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
    QMenuBar,
    QMenu,
)
from PyQt6.QtCore import Qt
from PyQt6.QtGui import QKeySequence, QShortcut

from gui.views.dock_manager import DockManager
from gui.views.document_area import DocumentArea
from gui.views import dock_registry
from gui.workers import LandingLoadWorker, RosterLoadWorker
from gui.models import TeamEntry, TeamRosterBundle
from gui.availability_table import AvailabilityTable
from planning import availability_store
from gui.services.layout_persistence import LayoutPersistenceService
from gui.services.command_registry import global_command_registry
from gui.services.shortcut_registry import global_shortcut_registry
from gui.views.shortcut_cheatsheet import ShortcutCheatSheetDialog
from gui.services.dock_style import DockStyleHelper
from gui.services.focus_style import install_focus_ring
from gui.views.command_palette import CommandPaletteDialog
from db import rebuild_database, ingest_path  # type: ignore
import sqlite3


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

        # Layout persistence (Milestone 2.3)
        self._layout_service = LayoutPersistenceService(base_dir=self.data_dir)

        self.dock_manager = DockManager()
        self._register_docks()
        self._build_document_area()
        self._create_initial_docks()
        self._load_landing()
        # Capture *default* pristine snapshot BEFORE applying any previously saved layout
        try:
            self._pristine_geometry = bytes(self.saveGeometry())  # type: ignore[attr-defined]
            self._pristine_state = bytes(self.saveState())  # type: ignore[attr-defined]
        except Exception:
            self._pristine_geometry = None
            self._pristine_state = None
        # Attempt to restore previous layout (non-fatal). If it succeeds, snapshot still reflects defaults.
        self._layout_service.load_layout("main", self)
        self._build_menus()
        # Apply dock styling enhancements (Milestone 2.6)
        try:
            DockStyleHelper().apply_to_existing_docks(self)
        except Exception:
            pass  # non-fatal styling failure
        self._dock_style_helper = DockStyleHelper()
        self._install_dock_event_hooks()
        # Install focus ring styling (Milestone 2.7)
        try:
            install_focus_ring(self)
        except Exception:
            pass

    # Registration ---------------------------------------------------
    def _register_docks(self):
        # Allow plugins to register additional docks beforehand
        dock_registry.run_plugin_hooks()
        # Provide core factories mapping for ensure_core_docks_registered
        factories = {
            "navigation": self._build_navigation_dock,
            "availability": self._build_availability_dock,
            "detail": self._build_detail_dock,
            "stats": self._build_stats_dock,
            "planner": self._build_planner_dock,
            "logs": self._build_logs_dock,
        }
        dock_registry.ensure_core_docks_registered(factories)
        # Register all definitions with local DockManager
        for definition in dock_registry.iter_definitions():
            if not self.dock_manager.is_registered(definition.dock_id):
                self.dock_manager.register(definition.dock_id, definition.title, definition.factory)

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
        # Style new docks
        try:
            helper = DockStyleHelper()
            helper.create_title_bar(nav_dock)
            helper.create_title_bar(avail_dock)
        except Exception:
            pass
        for d in (nav_dock, avail_dock):
            try:
                d.topLevelChanged.connect(self._on_dock_top_level_changed)  # type: ignore
            except Exception:
                pass

    # Dock overlay preview (lightweight placeholder) -------------
    def _install_dock_event_hooks(self):
        if not hasattr(self, "findChildren"):
            return
        try:
            docks = self.findChildren(QDockWidget)  # type: ignore
            for d in docks:
                d.topLevelChanged.connect(self._on_dock_top_level_changed)  # type: ignore
        except Exception:
            pass

    def _on_dock_top_level_changed(self, floating: bool):  # pragma: no cover
        # Placeholder: We could show a subtle overlay when floating starts.
        if floating:
            try:
                self._dock_style_helper.show_overlay(self)
            except Exception:
                pass
        else:
            try:
                self._dock_style_helper.hide_overlay(self)
            except Exception:
                pass

    def _build_menus(self):
        mb = self.menuBar() if self.menuBar() else QMenuBar(self)
        view_menu = None
        help_menu = None
        for a in mb.actions():  # reuse if exists
            if a.text() == "&View":
                view_menu = a.menu()
            if a.text() == "&Help":
                help_menu = a.menu()
                break
        if view_menu is None:
            view_menu = QMenu("&View", self)
            mb.addMenu(view_menu)
        if help_menu is None:
            help_menu = QMenu("&Help", self)
            mb.addMenu(help_menu)
        # Add actions via convenience overload (returns QAction object)
        reset_action = view_menu.addAction("Reset Layout")
        reset_action.triggered.connect(self._on_reset_layout)  # type: ignore[attr-defined]
        palette_action = view_menu.addAction("Command Palette...")
        palette_action.triggered.connect(self._open_command_palette)  # type: ignore[attr-defined]
        cheatsheet_action = help_menu.addAction("Keyboard Shortcuts...")
        cheatsheet_action.triggered.connect(self._open_shortcut_cheatsheet)  # type: ignore[attr-defined]
        # Global shortcut (in addition to menu for clarity)
        QShortcut(QKeySequence("Ctrl+P"), self, activated=self._open_command_palette)
        # Register shortcut in registry (id stable for future conflict detection)
        global_shortcut_registry.register(
            "commandPalette.show", "Ctrl+P", "Open Command Palette", category="Navigation"
        )
        global_command_registry.register(
            "help.shortcuts", "Show Keyboard Shortcuts", self._open_shortcut_cheatsheet
        )
        self._register_core_commands()

    def _on_reset_layout(self):
        # Delete persisted layout file
        self._layout_service.reset_layout("main")
        # If we have an in-memory pristine snapshot, restore it directly
        from PyQt6.QtCore import QByteArray  # local import

        restored_via_snapshot = False
        if getattr(self, "_pristine_geometry", None) and getattr(self, "_pristine_state", None):
            try:
                self.restoreGeometry(QByteArray(self._pristine_geometry))  # type: ignore[attr-defined]
                self.restoreState(QByteArray(self._pristine_state))  # type: ignore[attr-defined]
                restored_via_snapshot = True
            except Exception:
                restored_via_snapshot = False
        if not restored_via_snapshot:
            # Fallback: rebuild dock manager and recreate docks
            for dock in list(self.dock_manager.instances()):
                try:
                    self.removeDockWidget(dock)
                except Exception:
                    pass
            # Reinitialize dock manager completely to forget prior instances
            self.dock_manager = DockManager()
            self._register_docks()
            self._create_initial_docks()
        # Persist snapshot as new baseline
        try:
            self._layout_service.save_layout("main", self)
        except Exception:
            pass
        QMessageBox.information(self, "Layout Reset", "Layout restored to defaults.")

    # Command Palette ----------------------------------------------
    def _open_command_palette(self):
        dlg = CommandPaletteDialog(self)
        dlg.exec()

    def _register_core_commands(self):
        # Basic commands; ignore failures if already registered
        global_command_registry.register(
            "app.refreshTeams",
            "Refresh Teams",
            lambda: self._load_landing(),
            "Reload team list from source",
        )
        global_command_registry.register(
            "app.saveAvailability",
            "Save Availability",
            lambda: self._save_availability(),
            "Persist current availability state",
        )
        global_command_registry.register(
            "view.resetLayout",
            "Reset Layout",
            lambda: self._on_reset_layout(),
            "Restore default dock arrangement",
        )

        # Manual DB rebuild command (Milestone 3.8)
        def _rebuild_db():
            # For now create an in-memory DB and run rebuild using data_dir as HTML root.
            # Future: integrate shared app-level connection & progress dialog.
            conn = sqlite3.connect(":memory:")
            conn.execute("PRAGMA foreign_keys=ON")
            try:
                rebuild_database(conn, self.data_dir)
                QMessageBox.information(
                    self, "DB Rebuild", "Database rebuild completed (in-memory test)."
                )
            except Exception as e:  # pragma: no cover - GUI message path
                QMessageBox.critical(self, "DB Rebuild Failed", str(e))

        global_command_registry.register(
            "db.rebuild",
            "Rebuild Database (In-Memory)",
            _rebuild_db,
            "Drop & recreate schema then ingest all HTML (temporary in-memory run)",
        )

    # Shortcuts / Help --------------------------------------------
    def _open_shortcut_cheatsheet(self):
        dlg = ShortcutCheatSheetDialog(self)
        dlg.exec()

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

    # --- Core placeholder docks (Milestone 2.2) --------------------
    def _build_detail_dock(self) -> QWidget:
        w = QWidget()
        lay = QVBoxLayout(w)
        lay.addWidget(QLabel("Detail Dock Placeholder (future: contextual detail view)"))
        return w

    def _build_stats_dock(self) -> QWidget:
        w = QWidget()
        lay = QVBoxLayout(w)
        lay.addWidget(QLabel("Stats Dock Placeholder (future: KPIs, charts)"))
        return w

    def _build_planner_dock(self) -> QWidget:
        w = QWidget()
        lay = QVBoxLayout(w)
        lay.addWidget(QLabel("Planner Dock Placeholder (future: lineup optimization)"))
        return w

    def _build_logs_dock(self) -> QWidget:
        w = QWidget()
        lay = QVBoxLayout(w)
        lay.addWidget(QLabel("Logs Dock Placeholder (future: live logging panel)"))
        return w

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

    # Qt event overrides -------------------------------------------
    def closeEvent(self, event):  # type: ignore[override]
        # Save layout before closing
        try:
            self._layout_service.save_layout("main", self)
        finally:
            super().closeEvent(event)


__all__ = ["MainWindow"]
