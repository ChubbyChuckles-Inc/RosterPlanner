import pytest
from PyQt6.QtWidgets import QApplication

from gui.views.main_window import MainWindow
from gui.models import TeamEntry, PlayerEntry, MatchDate, TeamRosterBundle


@pytest.fixture(scope="module")
def app():  # pragma: no cover - Qt app fixture
    import sys

    app = QApplication.instance() or QApplication(sys.argv)  # type: ignore
    yield app


def test_player_detail_tab_open(app, tmp_path):
    win = MainWindow(club_id=1, season=2025, data_dir=str(tmp_path))
    team = TeamEntry(team_id="tP", name="Players United", division="Div PU")
    players = [
        PlayerEntry(team_id="tP", name="Alice", live_pz=1500),
        PlayerEntry(team_id="tP", name="Bob", live_pz=1480),
    ]
    matches = [MatchDate(iso_date="2025-09-21", display="21.09.2025")]
    bundle = TeamRosterBundle(team=team, players=players, match_dates=matches)
    # Open team detail with bundle
    win.open_team_detail(team, bundle)
    doc_area = getattr(win, "document_area")
    team_widget = doc_area.document_widget("team:tP")
    assert team_widget is not None

    # Simulate double-click on first player row programmatically
    # Directly invoke the slot on the view (bypassing Qt event system)
    team_widget._on_player_double_clicked(team_widget.roster_table.item(0, 0))

    # Player tab should be open
    player_doc_id = "player:tP:Alice"
    player_widget = doc_area.document_widget(player_doc_id)
    assert player_widget is not None, "Expected player detail tab to open"
    # Summary label should be set (placeholder history has entries)
    assert "entries" in player_widget.summary_label.text()
