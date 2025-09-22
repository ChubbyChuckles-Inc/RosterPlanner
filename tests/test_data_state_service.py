from gui.services.data_state_service import DataStateService
from gui.services.service_locator import services
import sqlite3


def _make_conn(empty: bool = True):
    conn = sqlite3.connect(":memory:")
    conn.executescript(
        """
        CREATE TABLE divisions(id TEXT PRIMARY KEY, name TEXT, level TEXT, category TEXT);
        CREATE TABLE clubs(id TEXT PRIMARY KEY, name TEXT);
        CREATE TABLE teams(id TEXT PRIMARY KEY, name TEXT, division_id TEXT, club_id TEXT);
        CREATE TABLE provenance(path TEXT PRIMARY KEY, sha1 TEXT NOT NULL);
        """
    )
    if not empty:
        conn.execute("INSERT INTO divisions(id,name) VALUES('div1','Division 1')")
        conn.execute("INSERT INTO teams(id,name,division_id) VALUES('t1','Team 1','div1')")
        conn.execute("INSERT INTO provenance(path,sha1) VALUES('file','abc')")
        conn.commit()
    return conn


def test_data_state_empty():
    conn = _make_conn(empty=True)
    services.register("sqlite_conn", conn, allow_override=True)
    st = DataStateService(conn).current_state()
    assert not st.has_data
    assert st.team_count == 0


def test_data_state_populated():
    conn = _make_conn(empty=False)
    services.register("sqlite_conn", conn, allow_override=True)
    st = DataStateService(conn).current_state()
    assert st.has_data
    assert st.team_count == 1
    assert st.provenance_entries == 1
