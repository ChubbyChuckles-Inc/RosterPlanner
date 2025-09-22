from gui.services.division_data_service import DivisionDataService
from gui.services.service_locator import services
from gui.models import DivisionStandingEntry
import sqlite3


def _setup_conn():
    conn = sqlite3.connect(":memory:")
    conn.executescript(
        """
        CREATE TABLE divisions(id TEXT PRIMARY KEY, name TEXT, level TEXT, category TEXT);
        CREATE TABLE teams(id TEXT PRIMARY KEY, name TEXT, division_id TEXT, club_id TEXT);
        CREATE TABLE matches(id TEXT PRIMARY KEY, division_id TEXT, home_team_id TEXT, away_team_id TEXT, iso_date TEXT, round INTEGER, home_score INTEGER, away_score INTEGER);
        CREATE TABLE players(id TEXT PRIMARY KEY, name TEXT, team_id TEXT, live_pz INTEGER);
        CREATE TABLE clubs(id TEXT PRIMARY KEY, name TEXT);
        """
    )
    # Division
    conn.execute("INSERT INTO divisions(id, name) VALUES (?, ?)", ("div1", "Test Division"))
    # Teams
    conn.executemany(
        "INSERT INTO teams(id, name, division_id) VALUES (?,?,?)",
        [
            ("t1", "Team One", "div1"),
            ("t2", "Team Two", "div1"),
            ("t3", "Team Three", "div1"),
        ],
    )
    # Matches (chronological) - scoring: W=2, D=1
    # 2025-09-10: t1 beats t2 (6-4)
    conn.execute(
        "INSERT INTO matches(id, division_id, home_team_id, away_team_id, iso_date, round, home_score, away_score) VALUES (?,?,?,?,?,?,?,?)",
        ("m1", "div1", "t1", "t2", "2025-09-10", 1, 6, 4),
    )
    # 2025-09-15: t1 draws t3 (5-5)
    conn.execute(
        "INSERT INTO matches(id, division_id, home_team_id, away_team_id, iso_date, round, home_score, away_score) VALUES (?,?,?,?,?,?,?,?)",
        ("m2", "div1", "t1", "t3", "2025-09-15", 2, 5, 5),
    )
    # 2025-09-20: t3 beats t2 (7-3)
    conn.execute(
        "INSERT INTO matches(id, division_id, home_team_id, away_team_id, iso_date, round, home_score, away_score) VALUES (?,?,?,?,?,?,?,?)",
        ("m3", "div1", "t3", "t2", "2025-09-20", 3, 7, 3),
    )
    conn.commit()
    return conn


def test_division_data_service_basic():
    conn = _setup_conn()
    services.register("sqlite_conn", conn, allow_override=True)
    svc = DivisionDataService()
    rows = svc.load_division_standings("div1")
    # Expect 3 teams
    assert len(rows) == 3
    # Order: Team Three (points 3 diff +4), Team One (points 3 diff +2), Team Two (0)
    assert rows[0].team_name == "Team Three"
    assert rows[0].points == 3
    assert (
        rows[0].wins == 1 and rows[0].draws == 1
    )  # win vs t2? Actually t3 has win vs t2 and draw vs t1
    assert rows[1].team_name == "Team One"
    assert rows[1].points == 3
    assert rows[1].wins == 1 and rows[1].draws == 1
    assert rows[2].team_name == "Team Two"
    assert rows[2].points == 0
    # Positions assigned sequentially
    assert [r.position for r in rows] == [1, 2, 3]
    # Recent form tokens length <=5 and matches expectations
    assert rows[0].recent_form in ("DW", "WD")  # order could vary if same-day ordering changes
    assert rows[1].recent_form in ("WD", "DW")
    assert rows[2].recent_form in ("LL", "L")  # two losses counted
