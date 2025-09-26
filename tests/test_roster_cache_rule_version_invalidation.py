"""Tests rule-version aware invalidation for RosterCacheService (Milestone 7.10.62).

Scenario:
 - Seed cache with rule_version = 1 and one team bundle.
 - Change active_rule_version to 2 (simulating new rule set published).
 - Next TeamDataService.load_team_bundle call should observe version change and clear cache;
   the returned bundle should be a new object instance.

We use an in-memory sqlite schema with minimal tables required by TeamDataService.
"""
from __future__ import annotations

import sqlite3

from gui.services.service_locator import services
from gui.services.roster_cache_service import RosterCacheService
from gui.services.team_data_service import TeamDataService
from gui.models import TeamEntry

SCHEMA = """
CREATE TABLE division(division_id INTEGER PRIMARY KEY, name TEXT, season INTEGER);
CREATE TABLE team(team_id INTEGER PRIMARY KEY, club_id INTEGER, division_id INTEGER, name TEXT);
CREATE TABLE club(club_id INTEGER PRIMARY KEY, name TEXT);
CREATE TABLE player(player_id INTEGER PRIMARY KEY, team_id INTEGER, full_name TEXT, live_pz INTEGER);
CREATE TABLE match(match_id INTEGER PRIMARY KEY, division_id INTEGER, home_team_id INTEGER, away_team_id INTEGER, match_date TEXT, round INTEGER, home_score INTEGER, away_score INTEGER);
CREATE TABLE id_map(entity_type TEXT, source_key TEXT, assigned_id INTEGER PRIMARY KEY AUTOINCREMENT, UNIQUE(entity_type, source_key));
"""

def _seed(conn: sqlite3.Connection):
    conn.executescript(SCHEMA)
    # Seed IDs
    conn.execute("INSERT INTO id_map(entity_type, source_key) VALUES('division','Div 1')")
    div_id = conn.execute("SELECT assigned_id FROM id_map WHERE source_key='Div 1'").fetchone()[0]
    conn.execute("INSERT INTO division(division_id, name, season) VALUES(?,?,2025)", (div_id, 'Div 1'))
    conn.execute("INSERT INTO id_map(entity_type, source_key) VALUES('team','Team A')")
    team_id = conn.execute("SELECT assigned_id FROM id_map WHERE source_key='Team A'").fetchone()[0]
    conn.execute(
        "INSERT INTO team(team_id, club_id, division_id, name) VALUES(?,?,?,?)",
        (team_id, None, div_id, 'A'),
    )
    for p in ['Alpha', 'Beta']:
        conn.execute("INSERT INTO id_map(entity_type, source_key) VALUES('player',?)", (p,))
        pid = conn.execute("SELECT assigned_id FROM id_map WHERE source_key=?", (p,)).fetchone()[0]
        conn.execute(
            "INSERT INTO player(player_id, team_id, full_name, live_pz) VALUES(?,?,?,?)",
            (pid, team_id, p, 1500),
        )
    conn.commit()
    return str(team_id), 'Div 1'


def test_rule_version_change_clears_cache():
    conn = sqlite3.connect(":memory:")
    team_id, div_name = _seed(conn)
    services.register("sqlite_conn", conn, allow_override=True)
    cache = RosterCacheService(capacity=4)
    services.register("roster_cache", cache, allow_override=True)
    services.register("active_rule_version", 1, allow_override=True)

    team_entry = TeamEntry(team_id=team_id, name='A', division=div_name, club_name=None)
    svc = TeamDataService(conn=conn)

    first = svc.load_team_bundle(team_entry)
    assert first is not None
    # Explicitly put to mirror integration test pattern (some paths skip auto-cache in minimal schema)
    cache.ensure_rule_version(services.try_get("active_rule_version"))
    cache.put(team_id, first)
    assert cache.last_rule_version == 1

    # Simulate rule set update
    services.register("active_rule_version", 2, allow_override=True)

    second = svc.load_team_bundle(team_entry)
    assert second is not None
    # Cache should have been cleared & repopulated; object identity must differ
    assert second is not first
    assert cache.last_rule_version == 2
    # New object produced under updated rule version (cache population is best-effort and validated indirectly by new object + version).
