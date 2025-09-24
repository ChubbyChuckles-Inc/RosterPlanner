"""GUI roster loading smoke test.

This test exercises the minimal path of:
 - Creating an in-memory SQLite DB
 - Applying schema
 - Inserting a division, team, placeholder player
 - Instantiating TeamDetailView and feeding a synthetic TeamRosterBundle
 - Ensuring no exceptions and the table reflects the player

If future regressions (e.g., display_name logic, roster_pending badge) cause crashes
when clicking a team, this test should catch them earlier without starting the full GUI.
"""

from __future__ import annotations

import sqlite3
import pytest

from db import schema as db_schema
from gui.models import TeamEntry, PlayerEntry, MatchDate, TeamRosterBundle
from gui.views.team_detail_view import TeamDetailView


@pytest.fixture
def app(qtbot):  # provide a QApplication via pytest-qt
    # qtbot fixture ensures a Qt application instance
    return qtbot


def test_team_detail_view_roster_smoke(app):
    # Setup in-memory DB (not strictly needed for this direct view test, but simulates environment)
    conn = sqlite3.connect(":memory:")
    db_schema.apply_schema(conn)

    team = TeamEntry(
        team_id="1",
        name="Test Team",
        division="Test Division",
        club_name="Club",
        roster_pending=True,
    )
    players = [PlayerEntry(team_id="1", name="Alice Example", live_pz=1234)]
    matches = [MatchDate(iso_date="2025-09-24", display="24.09.2025", time=None)]
    bundle = TeamRosterBundle(team=team, players=players, match_dates=matches)

    view = TeamDetailView()
    # Should not raise
    view.set_bundle(bundle)

    # Table should have one row with player name
    assert view.roster_table.rowCount() == 1
    assert view.roster_table.item(0, 0).text() == "Alice Example"
    # Title should include roster pending badge removal after real players loaded
    assert "Roster Pending" not in view.title_label.text()
