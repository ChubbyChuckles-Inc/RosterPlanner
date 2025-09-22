import pytest
from PyQt6.QtWidgets import QApplication

from gui.views.main_window import MainWindow
from gui.models import TeamEntry, PlayerEntry, MatchDate, TeamRosterBundle


@pytest.fixture(scope="module")
def app():  # pragma: no cover - Qt app fixture
    import sys

    app = QApplication.instance() or QApplication(sys.argv)  # type: ignore
    yield app


def test_open_team_detail_tab(app, tmp_path):
    # Create window with dummy identifiers
    win = MainWindow(club_id=1, season=2025, data_dir=str(tmp_path))
    # Simulate landing load by injecting teams directly (bypass thread worker for test determinism)
    team = TeamEntry(team_id="t1", name="Team One", division="Div A")
    win.teams = [team]
    # Open detail (will create tab)
    win.open_team_detail(team)
    # Document area should now contain a tab with id team:t1 (simulate by checking internal mapping)
    doc_area = getattr(win, "document_area")
    found = False
    for doc in doc_area._documents.values():  # type: ignore
        if doc.doc_id == "team:t1":
            found = True
            assert "Team" in doc.widget.title_label.text()
    assert found, "Expected team detail doc to be opened"
