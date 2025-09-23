import os
import sys
from PyQt6.QtWidgets import QApplication


def _app():
    os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
    return QApplication.instance() or QApplication(sys.argv)


def test_team_detail_skeleton_stops_after_bundle():
    app = _app()
    from gui.views.team_detail_view import TeamDetailView
    from gui.models import TeamRosterBundle, TeamEntry, PlayerEntry, MatchDate

    view = TeamDetailView()
    assert view.roster_skeleton.is_active()
    bundle = TeamRosterBundle(team=TeamEntry(team_id="t1", name="A", division="Div"), players=[PlayerEntry(team_id="t1", name="P1", live_pz=1200)], match_dates=[MatchDate(iso_date="2025-09-01", display="01.09.2025")])  # type: ignore[arg-type]
    view.set_bundle(bundle)
    app.processEvents()
    assert not view.roster_skeleton.is_active()


def test_division_table_skeleton_stops_on_set_rows():
    app = _app()
    from gui.views.division_table_view import DivisionTableView
    from gui.models import DivisionStandingEntry

    view = DivisionTableView()
    assert view.skeleton.is_active()
    row = DivisionStandingEntry(position=1, team_name="X", matches_played=1, wins=1, draws=0, losses=0, goals_for=3, goals_against=1, points=2, recent_form="W")  # type: ignore[arg-type]
    view.set_rows([row])
    app.processEvents()
    assert not view.skeleton.is_active()
