import pytest
from PyQt6.QtWidgets import QApplication

from gui.views.team_detail_view import TeamDetailView
from gui.models import TeamRosterBundle, TeamEntry, PlayerEntry, MatchDate


@pytest.fixture(scope="module")
def app():  # pragma: no cover
    import sys

    app = QApplication.instance() or QApplication(sys.argv)  # type: ignore
    yield app


def test_trend_column_population(app):
    view = TeamDetailView()
    bundle = TeamRosterBundle(
        team=TeamEntry(team_id="t1", name="Team", division="Div"),
        players=[
            PlayerEntry(team_id="t1", name="Alice", live_pz=1500),
            PlayerEntry(team_id="t1", name="Bob", live_pz=1490),
        ],
        match_dates=[MatchDate(iso_date="2025-09-21", display="21.09.2025")],
    )
    view.set_bundle(bundle)
    # Column count should be 3 now (Player, LivePZ, Trend)
    assert view.roster_table.columnCount() == 3
    # Trend column should not be empty
    for r in range(view.roster_table.rowCount()):
        item = view.roster_table.item(r, 2)
        assert item is not None
        assert item.text() != ""
