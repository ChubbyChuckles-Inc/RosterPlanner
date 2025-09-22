"""Navigation Tree Model (Milestone 4.1)

Provides a QAbstractItemModel for hierarchical navigation:
Season -> Division -> Team.

Roster (players) will be integrated in later milestones (5.x); for now leaf
nodes correspond to teams and contain the TeamEntry reference for selection.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import List, Optional, Any
from PyQt6.QtCore import Qt, QModelIndex, QAbstractItemModel
from gui.models import TeamEntry


@dataclass
class NavNode:
    label: str
    kind: str  # 'season' | 'division' | 'team'
    parent: Optional["NavNode"] = None
    team: Optional[TeamEntry] = None
    children: List["NavNode"] = None

    def __post_init__(self):
        if self.children is None:
            self.children = []

    def append(self, child: "NavNode"):
        child.parent = self
        self.children.append(child)

    def row(self) -> int:
        if not self.parent:
            return 0
        return self.parent.children.index(self)


class NavigationTreeModel(QAbstractItemModel):  # pragma: no cover - exercised via tests
    def __init__(self, season: int, teams: List[TeamEntry]):
        super().__init__()
        self._season = season
        self._root = NavNode(label=str(season), kind="season")
        # Group teams by division
        divisions: dict[str, List[TeamEntry]] = {}
        for t in teams:
            divisions.setdefault(t.division, []).append(t)
        for div, div_teams in sorted(divisions.items(), key=lambda x: x[0]):
            div_node = NavNode(label=div, kind="division")
            self._root.append(div_node)
            for team in sorted(div_teams, key=lambda x: x.name):
                div_node.append(NavNode(label=team.name, kind="team", team=team))

    # Required overrides
    def rowCount(self, parent: QModelIndex = QModelIndex()):  # type: ignore[override]
        node = self._node_from_index(parent)
        return len(node.children) if node else 0

    def columnCount(self, parent: QModelIndex = QModelIndex()):  # type: ignore[override]
        return 1

    def index(self, row: int, column: int, parent: QModelIndex = QModelIndex()):  # type: ignore[override]
        if column != 0 or row < 0:
            return QModelIndex()
        parent_node = self._node_from_index(parent)
        if not parent_node:
            return QModelIndex()
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

    def get_team_entry(self, index: QModelIndex) -> TeamEntry | None:
        if not index.isValid():
            return None
        node: NavNode = index.internalPointer()  # type: ignore
        return node.team


__all__ = ["NavigationTreeModel", "NavNode"]
