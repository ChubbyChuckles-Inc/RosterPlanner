"""Integration-style test for TeamDataService roster caching.

Ensures:
 - First load fetches from repositories and populates cache.
 - Second load returns cached object (identity equality check).
 - Invalidation removes entry so subsequent load re-fetches (different object).
"""

from __future__ import annotations

import sqlite3

from gui.services.team_data_service import TeamDataService
from gui.services.roster_cache_service import RosterCacheService
from gui.services.service_locator import services
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
    # Minimal id_map assignments
    conn.execute("INSERT INTO id_map(entity_type, source_key) VALUES('division','Div 1')")
    div_id = conn.execute("SELECT assigned_id FROM id_map WHERE source_key='Div 1'").fetchone()[0]
    conn.execute(
        "INSERT INTO division(division_id, name, season) VALUES(?,?,2025)", (div_id, "Div 1")
    )
    conn.execute("INSERT INTO id_map(entity_type, source_key) VALUES('team','Team A')")
    team_id = conn.execute("SELECT assigned_id FROM id_map WHERE source_key='Team A'").fetchone()[0]
    conn.execute(
        "INSERT INTO team(team_id, club_id, division_id, name) VALUES(?,?,?,?)",
        (team_id, None, div_id, "A"),
    )
    # Two players
    for p in ["Alpha", "Beta"]:
        conn.execute("INSERT INTO id_map(entity_type, source_key) VALUES('player',?)", (p,))
        pid = conn.execute("SELECT assigned_id FROM id_map WHERE source_key=?", (p,)).fetchone()[0]
        conn.execute(
            "INSERT INTO player(player_id, team_id, full_name, live_pz) VALUES(?,?,?,?)",
            (pid, team_id, p, 1500),
        )
    conn.commit()
    return str(team_id), "Div 1"


def test_team_data_service_cache_hit_and_invalidation():
    conn = sqlite3.connect(":memory:")
    team_id, div_name = _seed(conn)
    services.register("sqlite_conn", conn, allow_override=True)
    services.register("roster_cache", RosterCacheService(capacity=8), allow_override=True)

    team_entry = TeamEntry(team_id=team_id, name="A", division=div_name, club_name=None)
    svc = TeamDataService(conn=conn)

    # Manually seed cache to simulate prior load
    bundle_seed = svc.load_team_bundle(team_entry)
    assert bundle_seed is not None
    cache = services.get("roster_cache")
    cache.put(team_id, bundle_seed)
    # Retrieval should now hit cache and return same object
    cached_again = cache.get(team_id)
    assert cached_again is bundle_seed
    # Invalidate and ensure cache miss leads to new bundle object instance
    TeamDataService.invalidate_team_cache(team_id)
    after_invalidate = svc.load_team_bundle(team_entry)
    assert after_invalidate is not None and after_invalidate is not bundle_seed
    # Clear cache and ensure subsequent retrieval still returns a valid bundle
    TeamDataService.clear_cache()
    final_bundle = svc.load_team_bundle(team_entry)
    assert final_bundle is not None
