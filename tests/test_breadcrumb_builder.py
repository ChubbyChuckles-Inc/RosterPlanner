from gui.components.breadcrumb import BreadcrumbBuilder
from gui.navigation_tree_model import NavigationTreeModel, NavNode
from gui.models import TeamEntry
from PyQt6.QtCore import Qt


def _model():
    teams = [
        TeamEntry(team_id="t1", name="Alpha", division="DivA"),
        TeamEntry(team_id="t2", name="Beta", division="DivA"),
    ]
    return NavigationTreeModel(2025, teams)


def test_breadcrumb_build_for_team(qtbot):
    model = _model()
    builder = BreadcrumbBuilder()
    div_idx = model.index(0, 0)
    _ = model.rowCount(div_idx)  # force load
    team_idx = model.index(0, 0, div_idx)
    node: NavNode = model.data(team_idx, Qt.ItemDataRole.UserRole)
    text = builder.build_for_node(node)
    assert text == "2025 / DivA / Alpha"


def test_breadcrumb_empty_node(qtbot):
    builder = BreadcrumbBuilder()
    assert builder.build_for_node(None) == ""
