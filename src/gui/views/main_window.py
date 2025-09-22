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
    QTreeView,
    QLineEdit,
    QCheckBox,
    QGroupBox,
    QSizePolicy,
    QPlainTextEdit,
    QFileDialog,
)
from PyQt6.QtCore import Qt
from PyQt6.QtGui import QKeySequence, QShortcut, QClipboard, QAction

from gui.views.dock_manager import DockManager
from gui.views.document_area import DocumentArea
from gui.views import dock_registry
from gui.workers import LandingLoadWorker, RosterLoadWorker
from gui.models import TeamEntry, TeamRosterBundle
from gui.navigation_tree_model import NavigationTreeModel
from gui.navigation_filter_proxy import NavigationFilterProxyModel
from gui.availability_table import AvailabilityTable
from planning import availability_store
from gui.services.layout_persistence import LayoutPersistenceService
from gui.services.command_registry import global_command_registry
from gui.services.shortcut_registry import global_shortcut_registry
from gui.views.shortcut_cheatsheet import ShortcutCheatSheetDialog
from gui.services.dock_style import DockStyleHelper
from gui.services.focus_style import install_focus_ring
from gui.views.command_palette import CommandPaletteDialog
from gui.services.navigation_filter_persistence import (
    NavigationFilterPersistenceService,
    NavigationFilterState,
)
from gui.services.navigation_state_persistence import (
    NavigationStatePersistenceService,
    NavigationState,
)
from gui.services.permissions import PermissionService
from gui.components.breadcrumb import BreadcrumbBuilder
from gui.services.recent_teams import RecentTeamsTracker
from db import rebuild_database, ingest_path  # type: ignore
import sqlite3
from gui.views.rebuild_progress_dialog import RebuildProgressDialog


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
        # Navigation filter persistence (Milestone 4.3.1)
        self._nav_filter_service = NavigationFilterPersistenceService(base_dir=self.data_dir)
        self._nav_filter_state = self._nav_filter_service.load()
        # Navigation expansion/selection persistence (Milestone 4.4)
        self._nav_state_service = NavigationStatePersistenceService(base_dir=self.data_dir)
        self._nav_state = self._nav_state_service.load()
        # Permissions (Milestone 4.5.1 placeholder)
        self._perm_service = PermissionService()
        # Breadcrumb builder (Milestone 4.6)
        self._breadcrumb_builder = BreadcrumbBuilder()
        # Recently viewed teams tracker (Milestone 4.7)
        self._recent_tracker = RecentTeamsTracker()

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
            "recent": self._build_recent_dock,
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
            # Launch progress dialog using a temporary on-disk database file inside data_dir.
            db_file = os.path.join(self.data_dir, "rebuild_preview.sqlite")
            dlg = RebuildProgressDialog(db_file, self.data_dir, self)
            dlg.exec()

        global_command_registry.register(
            "db.rebuild",
            "Rebuild Database (Preview)",
            _rebuild_db,
            "Run database rebuild with progress dialog (preview on isolated file)",
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

        layout.addWidget(QLabel("Teams / Divisions"))
        self.search_input = QLineEdit()
        self.search_input.setPlaceholderText("Search teams...")
        layout.addWidget(self.search_input)
        # Breadcrumb label
        self.breadcrumb_label = QLabel("")
        self.breadcrumb_label.setObjectName("breadcrumbLabel")
        self.breadcrumb_label.setStyleSheet("color: #666; font-size: 11px;")
        layout.addWidget(self.breadcrumb_label)

        # Filter Chips (Milestone 4.3)
        chips_box = QGroupBox("Filters")
        chips_layout = QVBoxLayout(chips_box)
        # Division Types
        type_row = QHBoxLayout()
        self.chk_type_erw = QCheckBox("Erwachsene")
        self.chk_type_jugend = QCheckBox("Jugend")
        for chk in (self.chk_type_erw, self.chk_type_jugend):
            chk.stateChanged.connect(self._on_filter_chips_changed)  # type: ignore
            type_row.addWidget(chk)
        chips_layout.addLayout(type_row)
        # Levels
        lvl_row = QHBoxLayout()
        self.chk_lvl_bez = QCheckBox("Bezirksliga")
        self.chk_lvl_stadtliga = QCheckBox("Stadtliga")
        self.chk_lvl_stadtklasse = QCheckBox("Stadtklasse")
        for chk in (self.chk_lvl_bez, self.chk_lvl_stadtliga, self.chk_lvl_stadtklasse):
            chk.stateChanged.connect(self._on_filter_chips_changed)  # type: ignore
            lvl_row.addWidget(chk)
        chips_layout.addLayout(lvl_row)
        # Active
        self.chk_active_only = QCheckBox("Active Only")
        self.chk_active_only.stateChanged.connect(self._on_filter_chips_changed)  # type: ignore
        chips_layout.addWidget(self.chk_active_only)
        chips_box.setSizePolicy(QSizePolicy.Policy.Preferred, QSizePolicy.Policy.Maximum)
        layout.addWidget(chips_box)
        self.team_tree = QTreeView()
        self.team_tree.setHeaderHidden(True)
        self.team_tree.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self.team_tree.customContextMenuRequested.connect(self._on_nav_context_menu)  # type: ignore
        layout.addWidget(self.team_tree)

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

    def _build_recent_dock(self) -> QWidget:  # Milestone 4.7
        w = QWidget()
        lay = QVBoxLayout(w)
        lay.addWidget(QLabel("Recently Viewed Teams"))
        from PyQt6.QtWidgets import QListWidget

        self.recent_list = QListWidget()
        self.recent_list.itemActivated.connect(self._on_recent_item_activated)  # type: ignore
        lay.addWidget(self.recent_list)
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
        base_model = NavigationTreeModel(self.season, teams)
        # Wrap in filter proxy for search (Milestone 4.2)
        self.team_filter_proxy = NavigationFilterProxyModel()
        self.team_filter_proxy.setSourceModel(base_model)
        self.team_tree.setModel(self.team_filter_proxy)
        # Wire search input
        if hasattr(self, "search_input"):
            # Restore persisted search text
            if self._nav_filter_state.search:
                self.search_input.setText(self._nav_filter_state.search)
            self.search_input.textChanged.connect(self._on_search_text_changed)  # type: ignore
        # Expand root divisions by default (use proxy's first row)
        root_idx = self.team_filter_proxy.index(0, 0)
        if root_idx.isValid():  # pragma: no cover
            self.team_tree.expand(root_idx)
        self.team_tree.clicked.connect(self._on_tree_item_clicked)  # type: ignore
        # Apply persisted chip filters after model set
        self._apply_persisted_filters()
        # Restore expanded divisions & last selection
        self._restore_navigation_state()
        self._set_status(f"Loaded {len(teams)} teams")

    def _on_filter_chips_changed(self):  # pragma: no cover - GUI path
        proxy = getattr(self, "team_filter_proxy", None)
        if not proxy:
            return
        types = set()
        if self.chk_type_erw.isChecked():
            types.add("Erwachsene")
        if self.chk_type_jugend.isChecked():
            types.add("Jugend")
        levels = set()
        if self.chk_lvl_bez.isChecked():
            levels.add("Bezirksliga")
        if self.chk_lvl_stadtliga.isChecked():
            levels.add("Stadtliga")
        if self.chk_lvl_stadtklasse.isChecked():
            levels.add("Stadtklasse")
        proxy.setDivisionTypes(types)
        proxy.setLevels(levels)
        proxy.setActiveOnly(self.chk_active_only.isChecked())
        # Persist state
        self._nav_filter_state.division_types = types
        self._nav_filter_state.levels = levels
        self._nav_filter_state.active_only = self.chk_active_only.isChecked()
        self._nav_filter_service.save(self._nav_filter_state)

    def _on_search_text_changed(self, text: str):  # pragma: no cover - GUI path
        if hasattr(self, "team_filter_proxy"):
            self.team_filter_proxy.scheduleFilterPattern(text)
        self._nav_filter_state.search = text
        self._nav_filter_service.save(self._nav_filter_state)

    def _apply_persisted_filters(self):  # pragma: no cover - GUI path
        st = self._nav_filter_state
        # Set checkbox states without triggering multiple saves: block signals momentarily
        for chk, label in [
            (getattr(self, "chk_type_erw", None), "Erwachsene"),
            (getattr(self, "chk_type_jugend", None), "Jugend"),
            (getattr(self, "chk_lvl_bez", None), "Bezirksliga"),
            (getattr(self, "chk_lvl_stadtliga", None), "Stadtliga"),
            (getattr(self, "chk_lvl_stadtklasse", None), "Stadtklasse"),
        ]:
            if chk is None:
                continue
            want_checked = (
                (label in st.division_types)
                if label in ("Erwachsene", "Jugend")
                else (label in st.levels)
            )
            if chk.isChecked() != want_checked:
                chk.setChecked(want_checked)
        if hasattr(self, "chk_active_only") and self.chk_active_only.isChecked() != st.active_only:
            self.chk_active_only.setChecked(st.active_only)
        # Trigger filter application explicitly
        self._on_filter_chips_changed()

    # Roster + Players -----------------------------------------------
    def _load_selected_roster(self):
        sel = self.team_tree.currentIndex() if hasattr(self, "team_tree") else None
        if not sel or not sel.isValid():
            return
        # Unwrap proxy if present
        model_obj = self.team_tree.model()
        if isinstance(model_obj, NavigationFilterProxyModel):
            src: NavigationTreeModel = model_obj.sourceModel()  # type: ignore
            team = src.get_team_entry(model_obj.mapToSource(sel))
        else:
            src = model_obj  # type: ignore
            team = src.get_team_entry(sel)  # type: ignore
        if not team:
            return
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
            # Open or update team detail tab with full bundle
            self.open_team_detail(bundle.team, bundle)
        self.table.load(bundle.players, bundle.match_dates)
        team_id = bundle.team.team_id
        if team_id in self.av_state.teams:
            team_av = self.av_state.teams[team_id]
            # Future: apply saved statuses to the UI components
            _ = team_av  # placeholder usage
        self.av_state.ensure_team(team_id, [p.name for p in bundle.players])

    # Persistence ----------------------------------------------------
    def _save_availability(self):
        team: TeamEntry | None = None
        if hasattr(self, "team_tree"):
            idx = self.team_tree.currentIndex()
            if idx.isValid():
                model: NavigationTreeModel = self.team_tree.model()  # type: ignore
                team = model.get_team_entry(idx)
        for player, date_map in self.table.export_status().items():
            for date_iso, status in date_map.items():
                if team:
                    self.av_state.set_player_status(team.team_id, date_iso, player, status)
        availability_store.save(self.av_state, self.availability_path)
        self._set_status("Availability saved")
        QMessageBox.information(self, "Saved", "Availability data saved.")

    # Team Detail Tabs ----------------------------------------------
    def open_team_detail(self, team: TeamEntry, bundle: TeamRosterBundle | None = None):
        doc_id = f"team:{team.team_id}"
        if not hasattr(self, "document_area"):
            return
        from gui.views.team_detail_view import TeamDetailView
        from gui.services.column_visibility_persistence import ColumnVisibilityPersistenceService

        # Attempt to find existing roster bundle if we just loaded it (roster worker stores last bundle via table load)
        # For now we don't maintain a cache map; future optimization could store bundles in a dict.

        def factory():
            vis_service = ColumnVisibilityPersistenceService(self.data_dir)
            view = TeamDetailView(visibility_service=vis_service)
            # If we have players already in availability table referencing this team, synthesize a minimal bundle.
            # (Full bundle population occurs after roster worker finishes and calls open_team_detail again.)
            # This avoids empty interim view.
            try:
                # RosterLoadWorker triggers _on_roster_loaded which calls open_team_detail AFTER table load.
                # So by the time we call this, we may not yet have players; that's acceptable.
                pass
            except Exception:
                pass
            view.title_label.setText(f"Team: {team.name}")
            if bundle is not None:
                try:
                    view.set_bundle(bundle)
                except Exception:
                    pass
            return view

        existing = self.document_area.open_or_focus(doc_id, team.name, factory)
        # If already open and we now have a bundle, update it.
        if bundle is not None and isinstance(existing, TeamDetailView):
            try:
                existing.set_bundle(bundle)
            except Exception:
                pass

    # Tree interaction -------------------------------------------------
    def _on_tree_item_clicked(self, index):  # pragma: no cover - GUI path
        if not index.isValid():
            return
        model_obj = self.team_tree.model()
        if isinstance(model_obj, NavigationFilterProxyModel):
            src: NavigationTreeModel = model_obj.sourceModel()  # type: ignore
            team = src.get_team_entry(model_obj.mapToSource(index))
        else:
            team = model_obj.get_team_entry(index)  # type: ignore
        if team:
            self._load_selected_roster()
            # Persist last selected team id
            self._nav_state.last_selected_team_id = team.team_id
            self._nav_state_service.save(self._nav_state)
            # Update recent tracker
            self._recent_tracker.add(team.team_id)
            self._refresh_recent_list()
        # Update breadcrumb regardless of whether team found (divisions clear path)
        self._update_breadcrumb(index)

    # Context Menu (Milestone 4.5) ---------------------------------
    def _team_entry_from_index(self, index):  # pragma: no cover - GUI path
        if not index or not index.isValid():
            return None
        model_obj = self.team_tree.model()
        if isinstance(model_obj, NavigationFilterProxyModel):
            src: NavigationTreeModel = model_obj.sourceModel()  # type: ignore
            return src.get_team_entry(model_obj.mapToSource(index))
        return model_obj.get_team_entry(index)  # type: ignore

    def _on_nav_context_menu(self, pos):  # pragma: no cover - GUI path
        index = self.team_tree.indexAt(pos)
        team = self._team_entry_from_index(index)
        menu = QMenu(self)
        if self._perm_service.can_open_team():
            act_open = QAction("Open in New Tab", self)
            act_open.triggered.connect(lambda: team and self.open_team_detail(team))  # type: ignore
            menu.addAction(act_open)
        if team:
            if self._perm_service.can_copy_team_id():
                act_copy = QAction("Copy Team ID", self)
                act_copy.triggered.connect(lambda: self._copy_team_id(team.team_id))  # type: ignore
                menu.addAction(act_copy)
            if self._perm_service.can_export_team():
                act_export = QAction("Export Team JSON...", self)
                act_export.triggered.connect(lambda: self._export_team_json(team))  # type: ignore
                menu.addAction(act_export)
        menu.exec(self.team_tree.viewport().mapToGlobal(pos))

    def _copy_team_id(self, team_id: str):  # pragma: no cover - GUI path
        cb: QClipboard = self.application().clipboard() if hasattr(self, "application") else self.parent().clipboard()  # type: ignore
        try:
            QApplication = type(
                self
            ).parent  # placeholder to satisfy linter if QApplication not imported
        except Exception:  # pragma: no cover
            pass
        clipboard = self.window().clipboard() if hasattr(self.window(), "clipboard") else None  # type: ignore
        if clipboard:
            clipboard.setText(team_id)

    def _export_team_json(self, team):  # pragma: no cover - GUI path
        if not team:
            return
        dlg_path, _ = QFileDialog.getSaveFileName(
            self,
            "Export Team JSON",
            f"team_{team.team_id}.json",
            "JSON Files (*.json)",
        )
        if not dlg_path:
            return
        import json

        data = {
            "team_id": team.team_id,
            "name": team.name,
            "division": team.division,
            "season": self.season,
        }
        try:
            with open(dlg_path, "w", encoding="utf-8") as f:
                json.dump(data, f, indent=2)
            QMessageBox.information(self, "Export", f"Exported to {dlg_path}")
        except Exception as e:
            QMessageBox.warning(self, "Export Failed", str(e))

    # Qt event overrides -------------------------------------------
    def closeEvent(self, event):  # type: ignore[override]
        # Save layout before closing
        try:
            self._layout_service.save_layout("main", self)
            # Save navigation state snapshot on close
            self._snapshot_navigation_state()
            self._nav_state_service.save(self._nav_state)
        finally:
            super().closeEvent(event)

    # --- Navigation State Persistence (Milestone 4.4) ------------
    def _snapshot_navigation_state(self):  # pragma: no cover - GUI path
        if not hasattr(self, "team_tree"):
            return
        expanded = set()
        model = self.team_tree.model()
        # Iterate top-level divisions through proxy if used
        rows = model.rowCount()
        for r in range(rows):
            idx = model.index(r, 0)
            if self.team_tree.isExpanded(idx):
                # Map to source if proxy
                label = model.data(idx)
                expanded.add(label)
        self._nav_state.expanded_divisions = expanded

    def _restore_navigation_state(self):  # pragma: no cover - GUI path
        if not hasattr(self, "team_tree"):
            return
        model = self.team_tree.model()
        rows = model.rowCount()
        for r in range(rows):
            idx = model.index(r, 0)
            label = model.data(idx)
            if label in self._nav_state.expanded_divisions:
                self.team_tree.expand(idx)
        # Attempt to restore selection if team present
        if self._nav_state.last_selected_team_id:
            self._restore_last_selection()

    def _restore_last_selection(self):  # pragma: no cover - GUI path
        model = self.team_tree.model()
        rows = model.rowCount()
        for r in range(rows):
            div_idx = model.index(r, 0)
            # Expand to load children lazily
            self.team_tree.expand(div_idx)
            # Force child load via rowCount
            _ = model.rowCount(div_idx)
            child_rows = model.rowCount(div_idx)
            for c in range(child_rows):
                team_idx = model.index(c, 0, div_idx)
                # Map to team entry
                mobj = model
                entry = None
                if isinstance(mobj, NavigationFilterProxyModel):
                    src: NavigationTreeModel = mobj.sourceModel()  # type: ignore
                    entry = src.get_team_entry(mobj.mapToSource(team_idx))
                else:
                    entry = mobj.get_team_entry(team_idx)  # type: ignore
                if entry and entry.team_id == self._nav_state.last_selected_team_id:
                    self.team_tree.setCurrentIndex(team_idx)
                    self._update_breadcrumb(team_idx)
                    return

    # Breadcrumb (Milestone 4.6) -----------------------------------
    def _update_breadcrumb(self, index):  # pragma: no cover - GUI path
        if not hasattr(self, "breadcrumb_label"):
            return
        if not index or not index.isValid():
            self.breadcrumb_label.setText("")
            return
        model_obj = self.team_tree.model()
        src_node = None
        if isinstance(model_obj, NavigationFilterProxyModel):
            src: NavigationTreeModel = model_obj.sourceModel()  # type: ignore
            src_index = model_obj.mapToSource(index)
            node = src_index.internalPointer()  # type: ignore
            src_node = node
        else:
            node = index.internalPointer()  # type: ignore
            src_node = node
        breadcrumb = self._breadcrumb_builder.build_for_node(src_node)
        self.breadcrumb_label.setText(breadcrumb)

    # Recently Viewed (Milestone 4.7) ------------------------------
    def _refresh_recent_list(self):  # pragma: no cover - GUI path
        if not hasattr(self, "recent_list"):
            return
        self.recent_list.clear()
        # We need team names map
        by_id = {t.team_id: t for t in getattr(self, "teams", [])}
        for tid in self._recent_tracker.items():
            name = by_id.get(tid).name if tid in by_id else tid
            self.recent_list.addItem(f"{name} ({tid})")

    def _on_recent_item_activated(self, item):  # pragma: no cover - GUI path
        if not item:
            return
        text = item.text()
        if text.endswith(")") and "(" in text:
            tid = text[text.rfind("(") + 1 : -1]
        else:
            tid = text
        # Find team index and select
        model_obj = self.team_tree.model()
        rows = model_obj.rowCount()
        for r in range(rows):
            div_idx = model_obj.index(r, 0)
            _ = model_obj.rowCount(div_idx)
            child_rows = model_obj.rowCount(div_idx)
            for c in range(child_rows):
                t_idx = model_obj.index(c, 0, div_idx)
                entry = None
                if isinstance(model_obj, NavigationFilterProxyModel):
                    src: NavigationTreeModel = model_obj.sourceModel()  # type: ignore
                    entry = src.get_team_entry(model_obj.mapToSource(t_idx))
                else:
                    entry = model_obj.get_team_entry(t_idx)  # type: ignore
                if entry and entry.team_id == tid:
                    self.team_tree.setCurrentIndex(t_idx)
                    self._on_tree_item_clicked(t_idx)
                    return


__all__ = ["MainWindow"]
