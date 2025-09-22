from gui.views.split_team_compare_view import SplitTeamCompareView
from gui.models import TeamEntry, TeamRosterBundle


def _make_team(id_: int, name: str) -> TeamEntry:
    return TeamEntry(
        team_id=str(id_),
        name=name,
        division="Div X",
        division_type="Erwachsene",
        level="Bezirksliga",
        active=True,
    )


def test_split_team_compare_view_basic(qtbot, tmp_path):
    view = SplitTeamCompareView(base_dir=str(tmp_path))
    qtbot.addWidget(view)

    team_a = _make_team(1, "Alpha")
    team_b = _make_team(2, "Beta")

    # Minimal bundles (empty players/matches)
    bundle_a = TeamRosterBundle(team=team_a, players=[], match_dates=[])
    bundle_b = TeamRosterBundle(team=team_b, players=[], match_dates=[])

    view.set_bundles(team_a, bundle_a, team_b, bundle_b)

    left, right = view.current_team_names()
    assert left == "Alpha"
    assert right == "Beta"
    assert "Alpha" in view.header_label.text()
    assert "Beta" in view.header_label.text()

    # Ensure two child TeamDetailViews present in splitter
    assert view.splitter.count() == 2
