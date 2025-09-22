from gui.views.main_window import MainWindow
from gui.models import TeamEntry
from PyQt6.QtCore import Qt
import tempfile


def test_breadcrumb_updates_on_selection(qtbot):
    w = MainWindow(club_id=1, season=2025, data_dir=tempfile.mkdtemp())
    teams = [
        TeamEntry(team_id="t1", name="Alpha", division="DivA"),
        TeamEntry(team_id="t2", name="Beta", division="DivA"),
    ]
    w._on_landing_loaded(teams, "")
    model = w.team_tree.model()
    div_idx = model.index(0, 0)
    _ = model.rowCount(div_idx)
    team_idx = model.index(1, 0, div_idx)
    w._on_tree_item_clicked(team_idx)
    assert w.breadcrumb_label.text().endswith("DivA / Beta")
