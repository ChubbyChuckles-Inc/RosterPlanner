from gui.views.club_detail_view import ClubDetailView
from gui.models import TeamEntry


def _team(team_id: str, name: str, division: str) -> TeamEntry:
    return TeamEntry(team_id=team_id, name=name, division=division)


def test_club_detail_populates_qtable(qtbot):  # type: ignore
    view = ClubDetailView()
    qtbot.addWidget(view)
    teams = [
        _team("t1", "Alpha", "1 Bezirksliga Erwachsene"),
        _team("t2", "Beta", "1 Bezirksliga Erwachsene"),
        _team("t3", "Gamma", "1 Stadtliga Jugend 15"),
    ]
    view.set_teams(teams)
    assert view.team_count() == 3
    # Two divisions
    assert view.division_row_count() == 2
    # Meta label should include counts
    txt = view.meta_label.text()
    assert "Total Teams: 3" in txt
    assert "Erwachsene" in txt and "Jugend" in txt
