import pytest
from PyQt6.QtWidgets import QApplication

from gui.views.main_window import MainWindow
from gui.models import TeamEntry, PlayerEntry, MatchDate, TeamRosterBundle


@pytest.fixture(scope="module")
def app():  # pragma: no cover
    import sys

    app = QApplication.instance() or QApplication(sys.argv)  # type: ignore
    yield app


def test_team_detail_population(app, tmp_path):
    win = MainWindow(club_id=1, season=2025, data_dir=str(tmp_path))
    team = TeamEntry(team_id="tX", name="Alpha", division="Div X")
    players = [
        PlayerEntry(team_id="tX", name="A", live_pz=1500),
        PlayerEntry(team_id="tX", name="B", live_pz=1520),
        PlayerEntry(team_id="tX", name="C", live_pz=None),
    ]
    matches = [
        MatchDate(iso_date="2025-09-21", display="21.09.2025"),
        MatchDate(iso_date="2025-09-28", display="28.09.2025", time="18:00"),
    ]
    bundle = TeamRosterBundle(team=team, players=players, match_dates=matches)

    # Open with bundle
    win.open_team_detail(team, bundle)
    doc_area = getattr(win, "document_area")
    widget = doc_area.document_widget("team:tX")
    assert widget is not None
    # Title label reflects team name
    assert "Alpha" in widget.title_label.text()
    # Roster table rows
    assert widget.roster_table.rowCount() == 3
    # Summary label should mention avg
    assert "players" in widget.summary_label.text()
