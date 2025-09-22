"""SplitTeamCompareView (Milestone 5.7)

Provides a side-by-side comparison of two teams using a horizontal QSplitter.
Each pane hosts an embedded `TeamDetailView` instance so we leverage the
existing roster table, visibility persistence, and any future enhancements
there without duplication.

Design goals:
 - Lightweight container (no additional business logic)
 - Simple API: `set_left(team, bundle)` / `set_right(team, bundle)` or
   `set_bundles(team_a, bundle_a, team_b, bundle_b)` convenience method.
 - Expose child views for testing / future feature hooks (diffing, sync scrolling).

Future extensions (not in this milestone):
 - Synchronize column visibility / scrolling between panes.
 - Highlight differences (players only appearing in one roster, PZ deltas etc.).
 - Toolbar for quick swap / focus / export both.
"""

from __future__ import annotations
from typing import Optional
from PyQt6.QtWidgets import QWidget, QSplitter, QVBoxLayout, QLabel
from PyQt6.QtCore import Qt

from gui.models import TeamEntry, TeamRosterBundle
from gui.views.team_detail_view import TeamDetailView  # re-use existing implementation
from gui.services.column_visibility_persistence import ColumnVisibilityPersistenceService

__all__ = ["SplitTeamCompareView"]


class SplitTeamCompareView(QWidget):
    """Container view showing two `TeamDetailView` panes side-by-side.

    The view does not perform data fetching; the caller supplies already
    loaded roster bundles (or may call `set_left` / `set_right` incrementally).
    """

    def __init__(self, visibility_service_factory=None, base_dir: str | None = None, parent=None):
        super().__init__(parent)
        self._visibility_service_factory = visibility_service_factory or (
            lambda: ColumnVisibilityPersistenceService(base_dir or ".")
        )
        layout = QVBoxLayout(self)
        self.header_label = QLabel("Team Comparison")
        self.header_label.setObjectName("compareHeaderLabel")
        layout.addWidget(self.header_label)
        self.splitter = QSplitter(Qt.Orientation.Horizontal)
        layout.addWidget(self.splitter, 1)

        # Instantiate empty child views
        self.left_view = TeamDetailView(visibility_service=self._visibility_service_factory())
        self.right_view = TeamDetailView(visibility_service=self._visibility_service_factory())
        self.splitter.addWidget(self.left_view)
        self.splitter.addWidget(self.right_view)

        self._left_team: Optional[TeamEntry] = None
        self._right_team: Optional[TeamEntry] = None

    # --- Public API -------------------------------------------------
    def set_left(self, team: TeamEntry, bundle: TeamRosterBundle | None = None):
        self._left_team = team
        try:
            self.left_view.title_label.setText(f"Team: {team.name}")
        except Exception:
            pass
        if bundle is not None:
            try:
                self.left_view.set_bundle(bundle)
            except Exception:
                pass
        self._update_header()

    def set_right(self, team: TeamEntry, bundle: TeamRosterBundle | None = None):
        self._right_team = team
        try:
            self.right_view.title_label.setText(f"Team: {team.name}")
        except Exception:
            pass
        if bundle is not None:
            try:
                self.right_view.set_bundle(bundle)
            except Exception:
                pass
        self._update_header()

    def set_bundles(
        self,
        team_a: TeamEntry,
        bundle_a: TeamRosterBundle | None,
        team_b: TeamEntry,
        bundle_b: TeamRosterBundle | None,
    ):
        """Convenience to populate both panes in one call."""
        self.set_left(team_a, bundle_a)
        self.set_right(team_b, bundle_b)

    # --- Helpers ----------------------------------------------------
    def _update_header(self):  # pragma: no cover - simple UI
        if self._left_team and self._right_team:
            self.header_label.setText(
                f"Compare: {self._left_team.name}  vs  {self._right_team.name}"
            )
        elif self._left_team:
            self.header_label.setText(f"Compare: {self._left_team.name} vs ...")
        elif self._right_team:
            self.header_label.setText(f"Compare: ... vs {self._right_team.name}")
        else:
            self.header_label.setText("Team Comparison")

    # --- Introspection for tests -----------------------------------
    def current_team_names(self) -> tuple[str | None, str | None]:
        return (
            self._left_team.name if self._left_team else None,
            self._right_team.name if self._right_team else None,
        )
