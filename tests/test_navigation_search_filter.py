from __future__ import annotations

from PyQt6.QtCore import Qt

from gui.navigation_tree_model import NavigationTreeModel
from gui.navigation_filter_proxy import NavigationFilterProxyModel
from gui.models import TeamEntry


def _teams():
    return [
        TeamEntry(team_id="t1", name="Alpha Wolves", division="DivA"),
        TeamEntry(team_id="t2", name="Beta Bears", division="DivA"),
        TeamEntry(team_id="t3", name="Gamma Goats", division="DivB"),
        TeamEntry(team_id="t4", name="Delta Dolphins", division="DivB"),
    ]


def test_filter_empty_pattern_shows_all(qtbot):
    base = NavigationTreeModel(2025, _teams())
    proxy = NavigationFilterProxyModel()
    proxy.setSourceModel(base)
    # Root divisions count should match base after empty filter
    assert proxy.rowCount() == base.rowCount()


def test_filter_partial_case_insensitive(qtbot):
    base = NavigationTreeModel(2025, _teams())
    proxy = NavigationFilterProxyModel()
    proxy.setSourceModel(base)
    proxy.setFilterPattern("beta")
    # Iterate to find matching team label(s)
    matches = []
    for div_row in range(proxy.rowCount()):
        div_index = proxy.index(div_row, 0)
        # ensure divisions that have match remain
        for team_row in range(proxy.rowCount(div_index)):
            team_index = proxy.index(team_row, 0, div_index)
            label = proxy.data(team_index, Qt.ItemDataRole.DisplayRole)
            if label:
                matches.append(label)
    assert any("Beta Bears" == m for m in matches)
    # Non-matching unrelated team should not appear if division pruned (DivB retained only if any child matches)
    proxy.setFilterPattern("goats")
    matches = []
    for div_row in range(proxy.rowCount()):
        div_index = proxy.index(div_row, 0)
        for team_row in range(proxy.rowCount(div_index)):
            team_index = proxy.index(team_row, 0, div_index)
            label = proxy.data(team_index, Qt.ItemDataRole.DisplayRole)
            if label:
                matches.append(label)
    assert matches == ["Gamma Goats"]


def test_filter_no_results(qtbot):
    base = NavigationTreeModel(2025, _teams())
    proxy = NavigationFilterProxyModel()
    proxy.setSourceModel(base)
    proxy.setFilterPattern("zzzzz")
    # Expect zero divisions shown if nothing matches
    assert proxy.rowCount() == 0
