import sqlite3
from db.schema import apply_schema, get_existing_tables, SCHEMA_VERSION

CORE_TABLES = {
    "schema_meta",
    "club",
    "division",
    "team",
    "player",
    "match",
    "availability",
    "planning_scenario",
    "scenario_player",
}


def test_schema_apply_and_tables():
    conn = sqlite3.connect(":memory:")
    conn.execute("PRAGMA foreign_keys=ON")
    apply_schema(conn)
    tables = set(get_existing_tables(conn))
    assert CORE_TABLES.issubset(tables)
    # schema version recorded
    cur = conn.cursor()
    cur.execute("SELECT value FROM schema_meta WHERE key='schema_version'")
    row = cur.fetchone()
    assert row and row[0] == str(SCHEMA_VERSION)


def test_basic_inserts_and_fk_constraints():
    conn = sqlite3.connect(":memory:")
    conn.execute("PRAGMA foreign_keys=ON")
    apply_schema(conn)
    cur = conn.cursor()
    cur.execute("INSERT INTO club(club_id,name) VALUES(1,'Club A')")
    cur.execute(
        "INSERT INTO division(division_id,name,level,category,season) VALUES(10,'Div A','Bezirksliga','Erwachsene',2025)"
    )
    cur.execute("INSERT INTO team(team_id,club_id,division_id,name) VALUES(100,1,10,'Team A')")
    cur.execute("INSERT INTO player(player_id,team_id,full_name) VALUES(1000,100,'Player One')")
    # Availability unique constraint
    cur.execute(
        "INSERT INTO availability(player_id,date,status) VALUES(1000,'2025-09-22','available')"
    )
    try:
        cur.execute(
            "INSERT INTO availability(player_id,date,status) VALUES(1000,'2025-09-22','available')"
        )
        dup_allowed = True
    except Exception:
        dup_allowed = False
    assert dup_allowed is False
    # Scenario planning
    cur.execute("INSERT INTO planning_scenario(scenario_id,name) VALUES(1,'Scenario 1')")
    cur.execute("INSERT INTO scenario_player(scenario_id,player_id) VALUES(1,1000)")
    conn.commit()
    # Cascade behavior: delete player -> availability removed
    cur.execute("DELETE FROM player WHERE player_id=1000")
    cur.execute("SELECT COUNT(*) FROM availability")
    assert cur.fetchone()[0] == 0
