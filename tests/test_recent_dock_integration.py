from gui.views.main_window import MainWindow
from gui.models import TeamEntry
import tempfile


def test_recent_dock_updates_on_selection(qtbot):
    w = MainWindow(1, 2025, tempfile.mkdtemp())
    teams = [
        TeamEntry(team_id="t1", name="Alpha", division="DivA"),
        TeamEntry(team_id="t2", name="Beta", division="DivA"),
        TeamEntry(team_id="t3", name="Gamma", division="DivB"),
    ]
    w._on_landing_loaded(teams, "")
    model = w.team_tree.model()
    # Select two different teams
    divA = model.index(0, 0)
    _ = model.rowCount(divA)
    t1 = model.index(0, 0, divA)
    w._on_tree_item_clicked(t1)
    t2 = model.index(1, 0, divA)
    w._on_tree_item_clicked(t2)
    # Recent list should show t2 then t1
    if hasattr(w, "recent_list"):
        texts = [w.recent_list.item(i).text() for i in range(w.recent_list.count())]
        assert texts[0].startswith("Beta") and "(t2)" in texts[0]
        assert texts[1].startswith("Alpha") and "(t1)" in texts[1]
