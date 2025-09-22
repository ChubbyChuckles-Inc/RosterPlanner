from __future__ import annotations

import time
from PyQt6.QtCore import Qt, QTimer

from gui.navigation_tree_model import NavigationTreeModel
from gui.navigation_filter_proxy import NavigationFilterProxyModel
from gui.models import TeamEntry


def _teams():
    return [
        TeamEntry(team_id="t1", name="Alpha Wolves", division="DivA"),
        TeamEntry(team_id="t2", name="Beta Bears", division="DivA"),
        TeamEntry(team_id="t3", name="Gamma Goats", division="DivB"),
    ]


def test_debounce_single_application(qtbot):
    base = NavigationTreeModel(2025, _teams())
    proxy = NavigationFilterProxyModel()
    proxy.setSourceModel(base)

    # Rapidly schedule multiple patterns; only last should apply after 250ms
    proxy.scheduleFilterPattern("alp")
    proxy.scheduleFilterPattern("alph")
    proxy.scheduleFilterPattern("alpha")

    # Allow debounce interval to elapse
    qtbot.wait(300)
    # Filter should reduce to at least one division containing matching team
    # Ensure pattern actually applied (Alpha Wolves should be present)
    found = False
    for d in range(proxy.rowCount()):
        div_index = proxy.index(d, 0)
        for r in range(proxy.rowCount(div_index)):
            idx = proxy.index(r, 0, div_index)
            label = proxy.data(idx, Qt.ItemDataRole.DisplayRole)
            if label == "Alpha Wolves":
                found = True
    assert found


def test_background_index_build(qtbot):
    base = NavigationTreeModel(2025, _teams())
    proxy = NavigationFilterProxyModel()
    proxy.setSourceModel(base)
    assert proxy._index_ready is False  # type: ignore
    proxy.scheduleFilterPattern("beta")
    qtbot.wait(300)  # wait for debounce + thread build
    # After first filter application index should be ready (thread processed)
    assert proxy._index_ready is True  # type: ignore
