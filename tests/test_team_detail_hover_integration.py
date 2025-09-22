import pytest
from PyQt6.QtWidgets import QApplication

from gui.views.team_detail_view import TeamDetailView
from gui.models import TeamRosterBundle, TeamEntry, PlayerEntry, MatchDate


@pytest.fixture(scope="module")
def app():  # pragma: no cover
    import sys

    app = QApplication.instance() or QApplication(sys.argv)  # type: ignore
    yield app


def test_hover_sets_last_text(app):
    view = TeamDetailView()
    bundle = TeamRosterBundle(
        team=TeamEntry(team_id="t1", name="Team", division="Div"),
        players=[
            PlayerEntry(team_id="t1", name="Alice", live_pz=1500),
            PlayerEntry(team_id="t1", name="Bob", live_pz=None),
        ],
        match_dates=[MatchDate(iso_date="2025-09-21", display="21.09.2025")],
    )
    view.set_bundle(bundle)
    # Trigger hover on second player (index 1)
    view._on_cell_entered(1, 0)
    assert hasattr(view, "last_hover_text")
    assert "Bob" in view.last_hover_text
    assert "—" in view.last_hover_text
