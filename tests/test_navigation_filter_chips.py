from __future__ import annotations

from PyQt6.QtCore import Qt

from gui.navigation_tree_model import NavigationTreeModel
from gui.navigation_filter_proxy import NavigationFilterProxyModel
from gui.models import TeamEntry


def _teams():
    return [
        TeamEntry(team_id="t1", name="Alpha", division="1 Bezirksliga Erwachsene"),
        TeamEntry(team_id="t2", name="Beta", division="2 Stadtliga Erwachsene"),
        TeamEntry(team_id="t3", name="Gamma", division="1 Stadtklasse Erwachsene"),
        TeamEntry(team_id="t4", name="Delta", division="1 Stadtliga Jugend 15"),
    ]


def _all_team_labels(proxy):
    labels = []
    for d in range(proxy.rowCount()):
        div_index = proxy.index(d, 0)
        for r in range(proxy.rowCount(div_index)):
            team_index = proxy.index(r, 0, div_index)
            lbl = proxy.data(team_index, Qt.ItemDataRole.DisplayRole)
            if lbl:
                labels.append(lbl)
    return sorted(labels)


def test_filter_division_type_jugend_only(qtbot):
    base = NavigationTreeModel(2025, _teams())
    proxy = NavigationFilterProxyModel()
    proxy.setSourceModel(base)
    # Apply Jugend only
    proxy.setDivisionTypes({"Jugend"})
    labels = _all_team_labels(proxy)
    assert labels == ["Delta"]


def test_filter_level_bezirksliga_only(qtbot):
    base = NavigationTreeModel(2025, _teams())
    proxy = NavigationFilterProxyModel()
    proxy.setSourceModel(base)
    proxy.setLevels({"Bezirksliga"})
    labels = _all_team_labels(proxy)
    assert labels == ["Alpha"]


def test_filter_combined_type_and_level(qtbot):
    base = NavigationTreeModel(2025, _teams())
    proxy = NavigationFilterProxyModel()
    proxy.setSourceModel(base)
    proxy.setDivisionTypes({"Erwachsene"})
    proxy.setLevels({"Stadtliga"})
    labels = _all_team_labels(proxy)
    # Erwachsene + Stadtliga -> Beta only (exclude Delta Jugend)
    assert labels == ["Beta"]
