import pytest
from PyQt6.QtWidgets import QApplication
import sys
from gui.views.division_table_view import DivisionTableView
from gui.models import DivisionStandingEntry


@pytest.fixture(scope="module", autouse=True)
def _qapp():
    app = QApplication.instance() or QApplication(sys.argv)
    yield app


def test_division_table_empty_state_activation():
    view = DivisionTableView()
    # Initially no rows set -> treat as empty state active after explicit set
    view.set_rows([])
    assert view.is_empty_state_active()
    # Populate with one row -> empty state off
    row = DivisionStandingEntry(position=1, team_name="Team A", matches_played=1, wins=1, draws=0, losses=0, goals_for=5, goals_against=1, points=2, recent_form="W")  # type: ignore[arg-type]
    view.set_rows([row])
    assert not view.is_empty_state_active()
    # Clear again -> active
    view.set_rows([])
    assert view.is_empty_state_active()
