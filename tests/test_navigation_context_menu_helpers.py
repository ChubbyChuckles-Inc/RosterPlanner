from gui.views.main_window import MainWindow
from gui.models import TeamEntry
from gui.navigation_tree_model import NavigationTreeModel
from PyQt6.QtWidgets import QApplication
import tempfile
import os

# These tests exercise helper logic indirectly without invoking actual GUI context menu popup.


def _dummy_window(qtbot):
    w = MainWindow(club_id=1, season=2025, data_dir=tempfile.mkdtemp())
    return w


def test_team_entry_from_index_lookup(qtbot):
    w = _dummy_window(qtbot)
    # Simulate landing loaded
    teams = [
        TeamEntry(team_id="t1", name="Alpha", division="DivA"),
        TeamEntry(team_id="t2", name="Beta", division="DivA"),
    ]
    w._on_landing_loaded(teams, "")
    # Expand first division and access team
    model = w.team_tree.model()
    div_idx = model.index(0, 0)
    # Force load
    _ = model.rowCount(div_idx)
    team_idx = model.index(0, 0, div_idx)
    team = w._team_entry_from_index(team_idx)
    assert team and team.team_id == "t1"


def test_export_team_json(tmp_path, qtbot, monkeypatch):
    w = _dummy_window(qtbot)
    teams = [TeamEntry(team_id="t3", name="Gamma", division="DivB")]
    w._on_landing_loaded(teams, "")
    export_path = tmp_path / "team_t3.json"

    # Monkeypatch QFileDialog to return path
    from gui.views import main_window as mw_mod

    def fake_get_save_file_name(*args, **kwargs):
        return str(export_path), "json"

    monkeypatch.setattr(
        mw_mod.QFileDialog, "getSaveFileName", staticmethod(fake_get_save_file_name)
    )

    # Monkeypatch QMessageBox to suppress dialogs
    monkeypatch.setattr(mw_mod.QMessageBox, "information", lambda *a, **k: None)

    team = teams[0]
    w._export_team_json(team)
    assert export_path.exists()
    import json

    data = json.loads(export_path.read_text(encoding="utf-8"))
    assert data["team_id"] == "t3"
    assert data["name"] == "Gamma"
