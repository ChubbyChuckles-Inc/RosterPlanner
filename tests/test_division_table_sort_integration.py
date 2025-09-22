import pytest
from PyQt6.QtWidgets import QApplication

from gui.views.division_table_view import DivisionTableView
from gui.models import DivisionStandingEntry


@pytest.fixture(scope="module")
def app():  # pragma: no cover
    import sys

    return QApplication.instance() or QApplication(sys.argv)  # type: ignore


def _rows():
    return [
        DivisionStandingEntry(
            position=1,
            team_name="Gamma",
            matches_played=10,
            wins=7,
            draws=1,
            losses=2,
            goals_for=40,
            goals_against=20,
            points=22,
            recent_form="WWDLW",
        ),
        DivisionStandingEntry(
            position=2,
            team_name="Alpha",
            matches_played=11,
            wins=6,
            draws=2,
            losses=3,
            goals_for=35,
            goals_against=25,
            points=20,
            recent_form="WLDLW",
        ),
        DivisionStandingEntry(
            position=3,
            team_name="Beta",
            matches_played=10,
            wins=6,
            draws=1,
            losses=3,
            goals_for=30,
            goals_against=22,
            points=20,
            recent_form="DWWLW",
        ),
    ]


def test_multi_column_sort_priority(app):
    view = DivisionTableView()
    view.set_rows(_rows())
    # Sort by points desc (col 7) then team name asc (col 1)
    view.apply_sort_priority([(7, False), (1, True)])
    names = [view.table.item(r, 1).text() for r in range(view.table.rowCount())]
    assert names == ["Gamma", "Alpha", "Beta"]  # Alpha before Beta within same points (20)
    # Now add matches played asc (col 2) as third criteria
    view.apply_sort_priority([(7, False), (1, True), (2, True)])
    names2 = [view.table.item(r, 1).text() for r in range(view.table.rowCount())]
    assert names2 == names  # order unchanged because earlier keys already decisive
