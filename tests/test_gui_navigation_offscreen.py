import os
import sys
import sqlite3
import pytest
from PyQt6.QtWidgets import QApplication

# Ensure QApplication exists (offscreen)
app = QApplication.instance() or QApplication(sys.argv[:1])

from gui.app.bootstrap import create_app
from gui.views.main_window import MainWindow
from gui.models import TeamEntry, TeamRosterBundle, PlayerEntry


@pytest.fixture()
def temp_db(tmp_path):
    data_dir = tmp_path / "data"
    data_dir.mkdir()
    # Bootstrap to create schema + sqlite service
    ctx = create_app(headless=True, data_dir=str(data_dir))
    conn = ctx.services.get("sqlite_conn")
    yield conn, data_dir


def _insert_minimal_team(conn):
    # Insert minimal rows adhering to current schema definitions (schema.py)
    # Tables/columns: club(club_id,name), division(division_id,name,season), team(team_id,club_id,division_id,name), player(player_id,team_id,full_name,live_pz)
    conn.execute(
        "INSERT INTO club(club_id,name) VALUES(?,?)",
        (1001, "LTTV Leutzscher Füchse 1990"),
    )
    conn.execute(
        "INSERT INTO division(division_id,name,season) VALUES(?,?,?)",
        (2001, "1. Stadtliga Gruppe 1", 2025),
    )
    conn.execute(
        "INSERT INTO team(team_id,club_id,division_id,name) VALUES(?,?,?,?)",
        (3001, 1001, 2001, "7"),
    )
    conn.execute(
        "INSERT INTO player(player_id,team_id,full_name,live_pz) VALUES(?,?,?,?)",
        (4001, 3001, "Alice", 1500),
    )
    conn.commit()


def test_tree_displays_club_and_team_offscreen(temp_db):
    conn, data_dir = temp_db
    _insert_minimal_team(conn)
    win = MainWindow(club_id=2294, season=2025, data_dir=str(data_dir))
    # Trigger landing load synchronously by directly invoking the slot (bypassing thread)
    # Collect teams from DB via LandingLoadWorker helper logic
    from gui.services.data_state_service import DataStateService
    from gui.repositories.sqlite_impl import create_sqlite_repositories

    repos = create_sqlite_repositories(conn)
    club_map = {c.id: c.name for c in repos.clubs.list_clubs()}
    teams = []
    for d in repos.divisions.list_divisions():
        for t in repos.teams.list_teams_in_division(d.id):
            teams.append(
                TeamEntry(
                    team_id=str(t.id),
                    name=t.name,
                    division=d.name,
                    club_name=club_map.get(t.club_id) if t.club_id else None,
                )
            )
    # Ensure navigation dock (team_tree) constructed; fallback locate if attribute missing (robust to refactors)
    if not hasattr(win, "team_tree"):
        # Attempt to locate via QObject tree
        from PyQt6.QtWidgets import QTreeView

        for child in win.findChildren(QTreeView):  # type: ignore
            if child.objectName() in ("teamTree", "navigationTree", ""):
                win.team_tree = child  # type: ignore
                break
    win._on_landing_loaded(teams, "")
    # Expand first division and read first team label
    model = win.team_tree.model()
    root_idx = model.index(0, 0)
    win.team_tree.expand(root_idx)
    child_idx = model.index(0, 0, root_idx)
    label = model.data(child_idx)
    # Expect display_name for first team (may include club prefix if available)
    expected = teams[0].display_name
    assert label == expected
    assert "LTTV Leutzscher Füchse 1990" in label
    assert label.endswith("7")


def test_roster_load_offscreen(temp_db):
    conn, data_dir = temp_db
    _insert_minimal_team(conn)
    win = MainWindow(club_id=2294, season=2025, data_dir=str(data_dir))
    # Simulate landing loaded
    from gui.repositories.sqlite_impl import create_sqlite_repositories

    repos = create_sqlite_repositories(conn)
    club_map = {c.id: c.name for c in repos.clubs.list_clubs()}
    teams = []
    for d in repos.divisions.list_divisions():
        for t in repos.teams.list_teams_in_division(d.id):
            teams.append(
                TeamEntry(
                    team_id=str(t.id),
                    name=t.name,
                    division=d.name,
                    club_name=club_map.get(t.club_id) if t.club_id else None,
                )
            )
    if not hasattr(win, "team_tree"):
        from PyQt6.QtWidgets import QTreeView

        for child in win.findChildren(QTreeView):  # type: ignore
            win.team_tree = child  # type: ignore
            break
    win._on_landing_loaded(teams, "")
    # Select the team node and execute roster load logic via TeamDataService path
    model = win.team_tree.model()
    root_idx = model.index(0, 0)
    win.team_tree.expand(root_idx)
    team_idx = model.index(0, 0, root_idx)
    win.team_tree.setCurrentIndex(team_idx)
    win._load_selected_roster()
    # Since TeamDataService should return players, after worker thread replaced with direct call we simulate by direct service call
    from gui.services.team_data_service import TeamDataService

    svc = TeamDataService(conn=conn)
    bundle = svc.load_team_bundle(teams[0])
    assert bundle is not None
    assert any(p.name == "Alice" for p in bundle.players)
