"""Navigation Tree Model (Milestone 4.1)

Provides a QAbstractItemModel for hierarchical navigation:
Season -> Division -> Team.

Roster (players) will be integrated in later milestones (5.x); for now leaf
nodes correspond to teams and contain the TeamEntry reference for selection.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import List, Optional, Any, Dict
from PyQt6.QtCore import Qt, QModelIndex, QAbstractItemModel
from gui.models import TeamEntry


@dataclass
class NavNode:
    """A node in the navigation hierarchy.

    For virtualization (Milestone 4.1.1) division nodes start *unloaded* and
    hold raw team references until first expansion / data access triggers
    population of child nodes.
    """

    label: str
    kind: str  # 'season' | 'division' | 'team'
    parent: Optional["NavNode"] = None
    team: Optional[TeamEntry] = None
    children: List["NavNode"] = field(default_factory=list)
    _loaded: bool = True  # divisions will toggle this to False initially
    _pending_teams: List[TeamEntry] | None = None  # raw teams for deferred creation

    def append(self, child: "NavNode"):
        child.parent = self
        self.children.append(child)

    def row(self) -> int:
        if not self.parent:
            return 0
        return self.parent.children.index(self)

    def ensure_loaded(self):
        """Populate children if this is an unloaded division node.

        This method is idempotent and safe to call repeatedly.
        """
        if self.kind != "division" or self._loaded:
            return
        if not self._pending_teams:
            # Mark loaded even if no teams (avoid repeated checks)
            self._loaded = True
            return
        for team in sorted(self._pending_teams, key=lambda x: x.name):
            self.append(NavNode(label=team.name, kind="team", team=team))
        self._pending_teams = None
        self._loaded = True


class NavigationTreeModel(QAbstractItemModel):  # pragma: no cover - exercised via tests
    def __init__(self, season: int, teams: List[TeamEntry]):
        super().__init__()
        self._season = season
        self._root = NavNode(label=str(season), kind="season")
        # Group teams by division (store raw list for virtualization)
        divisions: Dict[str, List[TeamEntry]] = {}
        for t in teams:
            divisions.setdefault(t.division, []).append(t)
        for div, div_teams in sorted(divisions.items(), key=lambda x: x[0]):
            div_node = NavNode(label=div, kind="division")
            # Mark division as not yet loaded; stash pending teams
            div_node._loaded = False
            div_node._pending_teams = list(div_teams)
            self._root.append(div_node)

    # Required overrides
    def rowCount(self, parent: QModelIndex = QModelIndex()):  # type: ignore[override]
        node = self._node_from_index(parent)
        if node.kind == "division" and not node._loaded:
            # Do *not* load until an actual row query occurs (this call is that trigger)
            self._load_division(node)
        return len(node.children) if node else 0

    def columnCount(self, parent: QModelIndex = QModelIndex()):  # type: ignore[override]
        return 1

    def index(self, row: int, column: int, parent: QModelIndex = QModelIndex()):  # type: ignore[override]
        if column != 0 or row < 0:
            return QModelIndex()
        parent_node = self._node_from_index(parent)
        if not parent_node:
            return QModelIndex()
        # Virtualization: if parent is an unloaded division and row is 0, load now
        if parent_node.kind == "division" and not parent_node._loaded:
            self._load_division(parent_node)
        if row >= len(parent_node.children):
            return QModelIndex()
        child = parent_node.children[row]
        return self.createIndex(row, column, child)

    def parent(self, index: QModelIndex):  # type: ignore[override]
        if not index.isValid():
            return QModelIndex()
        node: NavNode = index.internalPointer()  # type: ignore
        if not node or not node.parent or node.parent == self._root:
            return QModelIndex()
        parent = node.parent
        return self.createIndex(parent.row(), 0, parent)

    def data(self, index: QModelIndex, role: int = Qt.ItemDataRole.DisplayRole):  # type: ignore[override]
        if not index.isValid():
            return None
        node: NavNode = index.internalPointer()  # type: ignore
        if role == Qt.ItemDataRole.DisplayRole:
            return node.label
        if role == Qt.ItemDataRole.UserRole:
            return node
        return None

    def flags(self, index: QModelIndex):  # type: ignore[override]
        if not index.isValid():
            return Qt.ItemFlag.NoItemFlags
        node: NavNode = index.internalPointer()  # type: ignore
        flags = Qt.ItemFlag.ItemIsEnabled | Qt.ItemFlag.ItemIsSelectable
        if node.kind == "division":
            flags |= Qt.ItemFlag.ItemIsDragEnabled  # placeholder for future interactions
        return flags

    # Helpers
    def _node_from_index(self, index: QModelIndex | None) -> NavNode:
        if index is None or not index.isValid():
            return self._root
        return index.internalPointer()  # type: ignore

    # Internal -----------------------------------------------------
    def _load_division(self, node: NavNode):
        """Load (populate) a division node's team children lazily.

        Emits appropriate beginInsertRows/endInsertRows for the model view
        to update. Safe to call multiple times (no-op after first load).
        """
        if node._loaded:
            return
        pending = node._pending_teams or []
        if not pending:
            node._loaded = True
            node._pending_teams = None
            return
        # Insert all children in one batch
        self.beginInsertRows(self._create_index_for(node), 0, len(pending) - 1)
        node.ensure_loaded()
        self.endInsertRows()

    def _create_index_for(self, node: NavNode) -> QModelIndex:
        if node is self._root:
            return QModelIndex()
        parent = node.parent
        if not parent:
            return QModelIndex()
        return self.createIndex(parent.children.index(node), 0, parent)

    def get_team_entry(self, index: QModelIndex) -> TeamEntry | None:
        if not index.isValid():
            return None
        node: NavNode = index.internalPointer()  # type: ignore
        return node.team


__all__ = ["NavigationTreeModel", "NavNode"]
