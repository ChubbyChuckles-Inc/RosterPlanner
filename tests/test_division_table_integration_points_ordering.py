"""Integration test for Milestone 5.9.17

Ensures DivisionDataService + DivisionTableView (indirectly via service) can
surface correct ordering and points when ranking table HTML was ingested but
no match breakdown (all computed aggregates zero). The service should fall
back to division_ranking ordering & points (added fallback logic).
"""

from __future__ import annotations

import sqlite3
from pathlib import Path

from gui.services.ingestion_coordinator import IngestionCoordinator
from gui.services.division_data_service import DivisionDataService

RANKING_HTML = """<html><body><table>
<tr><th>Pos</th><th>Team</th><th>Pts</th></tr>
<tr><td>1</td><td>Team Alpha 1</td><td>12</td></tr>
<tr><td>2</td><td>Team Beta 2</td><td>9</td></tr>
<tr><td>3</td><td>Team Gamma 3</td><td>5</td></tr>
</table></body></html>"""

ROSTER_TMPL = """<html><body><table><tr><td>Spieler</td><td>Pos</td><td>X</td><td>LivePZ</td><td>Y</td><td>Z</td></tr>
<tr><td>#</td><td>1.</td><td>-</td><td>{player}</td><td>-</td><td>1500</td></tr>
</table></body></html>"""


def _seed_assets(base: Path):
    division = "1_Stadtliga_Gruppe_1"
    (base / f"ranking_table_{division}.html").write_text(RANKING_HTML, encoding="utf-8")
    # Minimal rosters (single player) just to register teams
    for team in ["Team_Alpha_1", "Team_Beta_2", "Team_Gamma_3"]:
        (base / f"team_roster_{division}_{team}.html").write_text(
            ROSTER_TMPL.format(player=team.replace("_", " ")), encoding="utf-8"
        )
    return division


def test_division_table_points_and_ordering(tmp_path):
    data_dir = tmp_path / "data"
    data_dir.mkdir()
    division = _seed_assets(data_dir)
    conn = sqlite3.connect(":memory:")
    # Singular schema
    conn.executescript(
        """
        CREATE TABLE division(division_id INTEGER PRIMARY KEY, name TEXT, season INTEGER, level TEXT, category TEXT);
        CREATE TABLE team(team_id INTEGER PRIMARY KEY, club_id INTEGER, division_id INTEGER, name TEXT);
        CREATE TABLE club(club_id INTEGER PRIMARY KEY, name TEXT);
        CREATE TABLE player(player_id INTEGER PRIMARY KEY, team_id INTEGER, full_name TEXT, live_pz INTEGER);
        CREATE TABLE match(match_id INTEGER PRIMARY KEY, division_id INTEGER, home_team_id INTEGER, away_team_id INTEGER, match_date TEXT, round INTEGER, home_score INTEGER, away_score INTEGER);
        CREATE TABLE division_ranking(division_id INTEGER, position INTEGER, team_name TEXT, points INTEGER, matches_played INTEGER, wins INTEGER, draws INTEGER, losses INTEGER, PRIMARY KEY(division_id, position));
        CREATE TABLE id_map(entity_type TEXT, source_key TEXT, assigned_id INTEGER PRIMARY KEY AUTOINCREMENT, UNIQUE(entity_type, source_key));
        CREATE TABLE provenance(path TEXT PRIMARY KEY, sha1 TEXT NOT NULL, last_ingested_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP, parser_version INTEGER DEFAULT 1);
        CREATE TABLE provenance_summary(id INTEGER PRIMARY KEY AUTOINCREMENT, ingested_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP, divisions INTEGER, teams INTEGER, players INTEGER, files_processed INTEGER, files_skipped INTEGER);
        """
    )
    ing = IngestionCoordinator(str(data_dir), conn)
    ing.run()

    svc = DivisionDataService(conn)
    standings = svc.load_division_standings(division.replace("_", " "))
    assert len(standings) == 3
    # Order must match ranking table points ordering
    assert [s.team_name for s in standings] == ["Team Alpha 1", "Team Beta 2", "Team Gamma 3"]
    assert [s.points for s in standings] == [12, 9, 5]
    # Positions assigned sequentially per fallback
    assert [s.position for s in standings] == [1, 2, 3]
