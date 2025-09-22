import pytest
from PyQt6.QtWidgets import QApplication

from gui.views.main_window import MainWindow
from gui.models import TeamEntry, PlayerEntry, MatchDate, TeamRosterBundle


@pytest.fixture(scope="module")
def app():  # pragma: no cover
    import sys

    app = QApplication.instance() or QApplication(sys.argv)  # type: ignore
    yield app


def make_bundle(team_id: str):
    team = TeamEntry(team_id=team_id, name="Team X", division="Div")
    players = [PlayerEntry(team_id=team_id, name="A", live_pz=1500)]
    matches = [MatchDate(iso_date="2025-09-21", display="21.09.2025")]
    return TeamRosterBundle(team=team, players=players, match_dates=matches)


def test_column_visibility_persisted(app, tmp_path):
    win = MainWindow(1, 2025, str(tmp_path))
    bundle = make_bundle("tCol")
    # Open detail and hide a column via action (simulate toggle handler directly)
    win.open_team_detail(bundle.team, bundle)
    widget = win.document_area.document_widget("team:tCol")
    # Ensure initial both visible
    assert widget.roster_table.isColumnHidden(0) is False
    assert widget.roster_table.isColumnHidden(1) is False
    # Simulate user toggling Player column off
    widget._on_column_toggled("player", False)
    assert widget.roster_table.isColumnHidden(0) is True

    # Recreate window (new MainWindow -> load visibility from disk)
    win2 = MainWindow(1, 2025, str(tmp_path))
    win2.open_team_detail(bundle.team, bundle)
    widget2 = win2.document_area.document_widget("team:tCol")
    # Player column should be hidden due to persisted state
    assert widget2.roster_table.isColumnHidden(0) is True
    # LivePZ should remain visible
    assert widget2.roster_table.isColumnHidden(1) is False
