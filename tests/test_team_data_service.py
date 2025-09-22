from __future__ import annotations

import sqlite3
from gui.services.team_data_service import TeamDataService
from gui.services.service_locator import services
from gui.models import TeamEntry


def _create_schema(conn: sqlite3.Connection):
    conn.executescript(
        """
        CREATE TABLE divisions(id TEXT PRIMARY KEY, name TEXT, level TEXT, category TEXT);
        CREATE TABLE clubs(id TEXT PRIMARY KEY, name TEXT);
        CREATE TABLE teams(id TEXT PRIMARY KEY, name TEXT, division_id TEXT, club_id TEXT);
        CREATE TABLE players(id TEXT PRIMARY KEY, name TEXT, team_id TEXT, live_pz INTEGER);
        CREATE TABLE matches(id TEXT PRIMARY KEY, division_id TEXT, home_team_id TEXT, away_team_id TEXT, iso_date TEXT, round INTEGER, home_score INTEGER, away_score INTEGER);
        """
    )
    conn.commit()


def test_team_data_service_loads_bundle():
    conn = sqlite3.connect(":memory:")
    _create_schema(conn)
    services.register("sqlite_conn", conn, allow_override=True)
    # Seed minimal data
    conn.execute("INSERT INTO divisions(id,name) VALUES(?,?)", ("div_a", "Div A"))
    conn.execute("INSERT INTO clubs(id,name) VALUES(?,?)", ("club1", "Club 1"))
    conn.execute(
        "INSERT INTO teams(id,name,division_id,club_id) VALUES(?,?,?,?)",
        ("team-1", "Alpha Team", "div_a", "club1"),
    )
    conn.execute(
        "INSERT INTO players(id,name,team_id,live_pz) VALUES(?,?,?,?)",
        ("p1", "Player One", "team-1", 1500),
    )
    conn.execute(
        "INSERT INTO matches(id,division_id,home_team_id,away_team_id,iso_date,round,home_score,away_score) VALUES(?,?,?,?,?,?,?,?)",
        ("m1", "div_a", "team-1", "team-1", "2025-09-01", 1, None, None),
    )
    conn.commit()

    svc = TeamDataService()
    team_entry = TeamEntry(team_id="team-1", name="Alpha Team", division="div_a")
    bundle = svc.load_team_bundle(team_entry)
    assert bundle is not None
    assert bundle.team.team_id == "team-1"
    assert len(bundle.players) == 1
    assert bundle.players[0].name == "Player One"
    assert len(bundle.match_dates) == 1
    assert bundle.match_dates[0].iso_date == "2025-09-01"
