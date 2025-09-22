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
from typing import Optional, List, Callable
from PyQt6.QtWidgets import (
    QWidget,
    QVBoxLayout,
    QLabel,
    QTableWidget,
    QTableWidgetItem,
    QListWidget,
    QGroupBox,
    QHBoxLayout,
    QToolButton,
    QMenu,
    QAction,
)
from PyQt6.QtCore import Qt

from gui.models import TeamRosterBundle, PlayerEntry, MatchDate
from gui.services.column_visibility_persistence import (
    ColumnVisibilityPersistenceService,
    ColumnVisibilityState,
)


class TeamDetailView(QWidget):
    """Widget showing team roster, matches, and summary metrics.

    The widget is intentionally slim; it does not fetch data itself but
    exposes ``set_bundle`` to accept a ``TeamRosterBundle`` prepared by
    the caller. This keeps the view free of repository logic and easy
    to unit test (populate with synthetic bundle instances).
    """

    def __init__(
        self,
        parent: Optional[QWidget] = None,
        *,
        visibility_service: ColumnVisibilityPersistenceService | None = None,
    ):
        super().__init__(parent)
        self._bundle: Optional[TeamRosterBundle] = None
        self._visibility_service = visibility_service
        self._col_state: ColumnVisibilityState | None = (
            visibility_service.load() if visibility_service else None
        )
        self._column_keys = ["player", "live_pz"]
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
        # Toolbar with column toggle
        toolbar = QHBoxLayout()
        self.col_button = QToolButton()
        self.col_button.setText("Columns")
        self.col_button.setPopupMode(QToolButton.ToolButtonPopupMode.InstantPopup)
        menu = QMenu(self.col_button)
        self._column_actions: dict[str, QAction] = {}
        labels = {"player": "Player", "live_pz": "LivePZ"}
        for key in self._column_keys:
            act = QAction(labels[key], menu)
            act.setCheckable(True)
            initial_visible = True
            if self._col_state:
                initial_visible = self._col_state.is_visible(key)
            act.setChecked(initial_visible)
            act.toggled.connect(lambda checked, k=key: self._on_column_toggled(k, checked))  # type: ignore
            menu.addAction(act)
            self._column_actions[key] = act
        self.col_button.setMenu(menu)
        toolbar.addWidget(self.col_button)
        toolbar.addStretch(1)
        roster_layout.addLayout(toolbar)
        self.roster_table = QTableWidget(0, 2)
        self.roster_table.setHorizontalHeaderLabels(["Player", "LivePZ"])  # minimal for now
        self.roster_table.horizontalHeader().setStretchLastSection(True)
        roster_layout.addWidget(self.roster_table)
        root.addWidget(roster_box)
        # Apply initial visibility if persisted
        self._apply_column_visibility()

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
        # Ensure visibility applied after population (header unaffected by row ops)
        self._apply_column_visibility()

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

    # Column visibility --------------------------------------------------
    def _on_column_toggled(self, key: str, visible: bool):  # pragma: no cover - GUI path
        col_index = self._column_keys.index(key)
        self.roster_table.setColumnHidden(col_index, not visible)
        if self._col_state is None:
            self._col_state = ColumnVisibilityState()
        self._col_state.set_visible(key, visible)
        if self._visibility_service:
            try:
                self._visibility_service.save(self._col_state)
            except Exception:
                pass

    def _apply_column_visibility(self):  # pragma: no cover - GUI path
        if not self._col_state:
            return
        for key in self._column_keys:
            col_index = self._column_keys.index(key)
            self.roster_table.setColumnHidden(col_index, not self._col_state.is_visible(key))

    # Accessors for tests -------------------------------------------------
    def bundle(self) -> Optional[TeamRosterBundle]:  # pragma: no cover - trivial
        return self._bundle


__all__ = ["TeamDetailView"]
