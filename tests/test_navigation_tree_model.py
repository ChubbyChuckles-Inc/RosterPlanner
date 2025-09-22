from __future__ import annotations

from gui.navigation_tree_model import NavigationTreeModel, NavNode
from gui.models import TeamEntry
from PyQt6.QtCore import Qt


def _teams():
    return [
        TeamEntry(team_id="t1", name="Alpha", division="DivA"),
        TeamEntry(team_id="t2", name="Beta", division="DivA"),
        TeamEntry(team_id="t3", name="Gamma", division="DivB"),
    ]


def test_navigation_tree_structure(qtbot):  # qtbot fixture assumed available if pytest-qt installed
    model = NavigationTreeModel(2025, _teams())
    # Root has divisions
    assert model.rowCount() == 2
    div0 = model.index(0, 0)
    div1 = model.index(1, 0)
    assert model.data(div0, Qt.ItemDataRole.DisplayRole) == "DivA"
    # DivA has two teams
    assert model.rowCount(div0) == 2
    team0 = model.index(0, 0, div0)
    node0 = model.data(team0, Qt.ItemDataRole.UserRole)
    assert isinstance(node0, NavNode)
    assert node0.kind == "team"
    # Team entry retrieval
    entry = model.get_team_entry(team0)
    assert entry and entry.name == "Alpha"


def test_team_lookup_leaf(qtbot):
    model = NavigationTreeModel(2025, _teams())
    div0 = model.index(0, 0)
    team1 = model.index(1, 0, div0)
    entry = model.get_team_entry(team1)
    assert entry and entry.name == "Beta"
