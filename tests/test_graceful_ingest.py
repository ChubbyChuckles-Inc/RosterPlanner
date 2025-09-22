import sqlite3

from gui.services.graceful_ingest import GracefulIngestService


def test_summarize_available_singular_schema():
    conn = sqlite3.connect(":memory:")
    cur = conn.cursor()
    # Create minimal singular schema
    cur.execute("CREATE TABLE division(division_id INTEGER PRIMARY KEY, name TEXT)")
    cur.execute("CREATE TABLE team(team_id INTEGER PRIMARY KEY, division_id INTEGER, name TEXT)")
    cur.execute(
        "CREATE TABLE player(player_id INTEGER PRIMARY KEY, team_id INTEGER, full_name TEXT)"
    )
    cur.execute("INSERT INTO division(division_id, name) VALUES(1, 'Div A')")
    cur.execute("INSERT INTO team(team_id, division_id, name) VALUES(10, 1, 'Team X')")
    cur.execute("INSERT INTO player(player_id, team_id, full_name) VALUES(100, 10, 'Alice')")
    conn.commit()

    summary = GracefulIngestService.summarize_available(conn)
    assert summary == {"Div A": {"teams": 1, "players": 1}}


def test_summarize_available_plural_schema():
    conn = sqlite3.connect(":memory:")
    cur = conn.cursor()
    # Create legacy plural schema
    cur.execute("CREATE TABLE divisions(id TEXT PRIMARY KEY, name TEXT)")
    cur.execute("CREATE TABLE teams(id TEXT PRIMARY KEY, division_id TEXT, name TEXT)")
    cur.execute("CREATE TABLE players(id TEXT PRIMARY KEY, team_id TEXT, full_name TEXT)")
    cur.execute("INSERT INTO divisions(id, name) VALUES('d1', 'Div B')")
    cur.execute("INSERT INTO teams(id, division_id, name) VALUES('t1', 'd1', 'Team Y')")
    cur.execute("INSERT INTO players(id, team_id, full_name) VALUES('p1', 't1', 'Bob')")
    conn.commit()

    summary = GracefulIngestService.summarize_available(conn)
    # Division key derived from id (since we select id,name but teams use division_id)
    assert summary == {"Div B": {"teams": 1, "players": 1}}
