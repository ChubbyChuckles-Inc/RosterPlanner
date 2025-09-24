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
)
from PyQt6.QtCore import Qt, QPoint, pyqtSignal
from PyQt6.QtWidgets import QToolTip
from PyQt6.QtGui import QAction

from gui.models import TeamRosterBundle, PlayerEntry, MatchDate
from gui.services.sparkline import SparklineBuilder
from gui.services.column_visibility_persistence import (
    ColumnVisibilityPersistenceService,
    ColumnVisibilityState,
)
from gui.components.skeleton_loader import SkeletonLoaderWidget


class TeamDetailView(QWidget):
    """Widget showing team roster, matches, and summary metrics.

    The widget is intentionally slim; it does not fetch data itself but
    exposes ``set_bundle`` to accept a ``TeamRosterBundle`` prepared by
    the caller. This keeps the view free of repository logic and easy
    to unit test (populate with synthetic bundle instances).
    """

    # Emitted when a player row is activated (double-click). Argument: player name.
    playerActivated = pyqtSignal(str)

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
        self._column_keys = ["player", "live_pz", "trend"]
        self._spark_builder = SparklineBuilder()
        self._build_ui()

    # UI -----------------------------------------------------------------
    def _build_ui(self):
        root = QVBoxLayout(self)
        self.title_label = QLabel("Team Detail")
        self.title_label.setObjectName("teamTitleLabel")
        # Styling (color/size/weight) now handled by global theme QSS via object name
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
        labels = {"player": "Player", "live_pz": "LivePZ", "trend": "Trend"}
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
        self.roster_table = QTableWidget(0, 3)
        self.roster_table.setHorizontalHeaderLabels(
            ["Player", "LivePZ", "Trend"]
        )  # trend sparkline
        self.roster_table.horizontalHeader().setStretchLastSection(True)
        # Force headers to be visible immediately (some styles delay painting until hover)
        try:
            hh = self.roster_table.horizontalHeader()
            vh = self.roster_table.verticalHeader()
            hh.setVisible(True)
            vh.setVisible(True)
            # Minimal stylesheet nudge to ensure immediate paint
            # Force layout / repaint
            hh.resizeSections(hh.ResizeMode.ResizeToContents)
            vh.resizeSections(vh.ResizeMode.ResizeToContents)
            hh.repaint(); vh.repaint()
        except Exception:
            pass
        roster_layout.addWidget(self.roster_table)
        # Double-click to open player detail
        try:
            self.roster_table.itemDoubleClicked.connect(self._on_player_double_clicked)  # type: ignore
        except Exception:
            pass
        root.addWidget(roster_box)
        # Skeleton for roster (will hide once bundle set)
        self.roster_skeleton = SkeletonLoaderWidget("table-row", rows=5)
        self.roster_skeleton.start()
        root.addWidget(self.roster_skeleton)
        # Enable cell tracking for hover tooltips
        try:
            self.roster_table.setMouseTracking(True)
            self.roster_table.cellEntered.connect(self._on_cell_entered)  # type: ignore
        except Exception:
            pass
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
        if bundle is None:  # defensive guard (should not happen)
            return
        self._bundle = bundle
        # Use display_name (includes club + suffix) for clearer context
        try:
            display_name = bundle.team.display_name  # type: ignore[attr-defined]
        except Exception:
            display_name = bundle.team.name
        # If roster has real players, clear roster_pending on the model to keep UI consistent
        if hasattr(bundle.team, "roster_pending"):
            if bundle.players and not (
                len(bundle.players) == 1 and bundle.players[0].name == "Placeholder Player"
            ):
                try:
                    bundle.team.roster_pending = False  # type: ignore[attr-defined]
                    display_name = bundle.team.display_name
                except Exception:
                    pass
        self.title_label.setText(f"Team: {display_name}")
        self._populate_roster(bundle.players)
        self._populate_matches(bundle.match_dates)
        self._populate_summary(bundle.players)
        # Stop skeleton once real data applied
        try:
            self.roster_skeleton.stop()
        except Exception:
            pass

    def _populate_roster(self, players: List[PlayerEntry]):
        self.roster_table.setRowCount(len(players))
        for row, p in enumerate(players):
            self.roster_table.setItem(row, 0, QTableWidgetItem(p.name))
            livepz_text = "" if p.live_pz is None else str(p.live_pz)
            self.roster_table.setItem(row, 1, QTableWidgetItem(livepz_text))
            # Placeholder trend sparkline (deterministic based on name hash for test stability)
            trend_values = self._generate_placeholder_trend(p)
            spark = self._spark_builder.build(trend_values)
            self.roster_table.setItem(row, 2, QTableWidgetItem(spark))
        # Ensure visibility applied after population (header unaffected by row ops)
        self._apply_column_visibility()

    def _generate_placeholder_trend(self, player: PlayerEntry) -> List[int]:
        # Deterministic pseudo-random small range values derived from player name for stable tests
        base = sum(ord(c) for c in player.name) % 20 + 5  # 5..24
        # Create 6 points with slight variation
        vals = [base + ((i * 3) % 7) - 3 for i in range(6)]
        return vals

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

    # Hover card (Milestone 5.1.2) ---------------------------------------
    def _build_player_hover_text(self, player: PlayerEntry) -> str:
        parts = [player.name]
        if player.live_pz is not None:
            parts.append(f"LivePZ: {player.live_pz}")
        else:
            parts.append("LivePZ: —")
        # Future expansion: add recent form, availability stats, etc.
        return " | ".join(parts)

    def _on_cell_entered(self, row: int, col: int):  # pragma: no cover - GUI path
        if not self._bundle:
            return
        if row < 0 or row >= len(self._bundle.players):
            return
        player = self._bundle.players[row]
        text = self._build_player_hover_text(player)
        # Expose last hover text for testing (non-Qt dependency path)
        self.last_hover_text = text  # type: ignore
        try:
            pos = self.mapToGlobal(self.roster_table.viewport().mapFromParent(QPoint(0, 0)))  # type: ignore
            QToolTip.showText(pos, text, self.roster_table)
        except Exception:
            pass

    def _on_player_double_clicked(self, item):  # pragma: no cover - GUI path
        if not item:
            return
        row = item.row()
        if self._bundle and 0 <= row < len(self._bundle.players):
            name = self._bundle.players[row].name
            try:
                self.playerActivated.emit(name)
            except Exception:
                pass

    # Accessors for tests -------------------------------------------------
    def bundle(self) -> Optional[TeamRosterBundle]:  # pragma: no cover - trivial
        return self._bundle

    # Export integration (Milestone 5.6) ---------------------------------
    def get_export_rows(self):  # pragma: no cover - simple
        headers = ["Player", "LivePZ", "Trend"]
        rows: list[list[str]] = []
        for r in range(self.roster_table.rowCount()):
            row_vals: list[str] = []
            for c in range(self.roster_table.columnCount()):
                it = self.roster_table.item(r, c)
                row_vals.append(it.text() if it else "")
            rows.append(row_vals)
        return headers, rows

    def get_export_payload(self):  # pragma: no cover - simple
        if not self._bundle:
            return {"team": None, "players": []}
        return {
            "team": self._bundle.team.name,
            "players": [
                {
                    "name": p.name,
                    "live_pz": p.live_pz,
                    "trend": (
                        self.roster_table.item(i, 2).text()
                        if self.roster_table.item(i, 2)
                        else None
                    ),
                }
                for i, p in enumerate(self._bundle.players)
            ],
            "matches": [m.display for m in self._bundle.match_dates],
        }


__all__ = ["TeamDetailView"]
