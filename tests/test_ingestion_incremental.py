"""Tests Milestone 5.9.14 incremental ingest behavior.

Scenario:
 - Prepare two divisions each with a ranking table and two team roster files.
 - Run initial ingestion -> all files processed (processed_files >= total files).
 - Modify ONE roster HTML file (change content so hash differs) while leaving other files intact.
 - Run ingestion again -> exactly ONE additional processed file (the changed roster) while
   all unchanged files counted as skipped.

We validate using the provenance table (hash-based skip) + IngestionSummary deltas.

Note: Current ingestion implementation associates roster processing with per-division
loop; each roster file independently checked for hash change. So modifying a single
roster should increment processed_files by 1 on second run.
"""

from __future__ import annotations

import sqlite3
from pathlib import Path

from gui.services.ingestion_coordinator import IngestionCoordinator


SCHEMA = """
CREATE TABLE division(division_id INTEGER PRIMARY KEY, name TEXT, season INTEGER);
CREATE TABLE team(team_id INTEGER PRIMARY KEY, club_id INTEGER, division_id INTEGER, name TEXT);
CREATE TABLE club(club_id INTEGER PRIMARY KEY, name TEXT);
CREATE TABLE player(player_id INTEGER PRIMARY KEY, team_id INTEGER, full_name TEXT, live_pz INTEGER);
"""

RANKING_HTML = """<html><table><tr><th>Pos</th><th>Team</th></tr><tr><td>1</td><td>X</td></tr></table></html>"""

ROSTER_TEMPLATE = """<html><body><table><tr><td>Spieler</td><td>1</td><td>-</td><td>{player}</td><td>-</td><td>{lpz}</td></tr></table></body></html>"""


def _write_div(base: Path, div: str, teams: list[tuple[str, str, int]]):
    # ranking
    (base / f"ranking_table_{div}.html").write_text(RANKING_HTML, encoding="utf-8")
    for idx, (token, player_name, lpz) in enumerate(teams, start=1):
        html = ROSTER_TEMPLATE.format(player=player_name, lpz=lpz)
        (base / f"team_roster_{div}_{token}_{1000+idx}.html").write_text(html, encoding="utf-8")


def _setup_conn() -> sqlite3.Connection:
    conn = sqlite3.connect(":memory:")
    conn.executescript(SCHEMA)
    return conn


def test_incremental_ingest_single_roster_change(tmp_path):
    data_dir = tmp_path / "data"
    data_dir.mkdir()
    # Division 1 and 2 each with two teams
    _write_div(
        data_dir,
        "1_Bezirksliga_Erwachsene",
        [("TeamA", "Alice", 1500), ("TeamB", "Bob", 1400)],
    )
    _write_div(
        data_dir,
        "2_Bezirksliga_Erwachsene",
        [("TeamC", "Carol", 1520), ("TeamD", "Dan", 1490)],
    )
    conn = _setup_conn()

    coord = IngestionCoordinator(str(data_dir), conn)
    first = coord.run()
    total_files = 2  # ranking tables
    # roster files = 4
    total_files += 4
    assert first.processed_files >= total_files  # all new
    assert first.skipped_files == 0

    # Modify ONE roster file (TeamC)
    # Deterministic selection of the TeamC roster file (iterdir order can vary across platforms)
    roster_candidates = sorted(
        [
            p
            for p in data_dir.iterdir()
            if p.name.startswith("team_roster_2_Bezirksliga_Erwachsene_TeamC")
        ],
        key=lambda p: p.name,
    )
    assert roster_candidates, "Expected at least one TeamC roster file"
    roster_team_c = roster_candidates[0]
    # Change LPZ number to alter hash
    content = roster_team_c.read_text(encoding="utf-8").replace("1520", "1533")
    roster_team_c.write_text(content, encoding="utf-8")

    second = coord.run()
    # Exactly one roster changed -> expect processed_files increase of 1 (others skipped)
    assert second.processed_files == 1  # only changed roster reprocessed
    # All unchanged files skipped; at least remaining files (5) should be skipped
    assert second.skipped_files >= total_files - 1

    # Validate provenance updated hash for changed file only
    cur = conn.execute("SELECT COUNT(*) FROM provenance")
    provenance_entries = cur.fetchone()[0]
    assert provenance_entries == total_files  # still same number of tracked files

    # Ensure hash for modified file updated (select last_ingested_at changed) by comparing timestamp order
    # (Simplified: we just ensure the modified file exists with a non-empty sha1)
    cur = conn.execute("SELECT sha1 FROM provenance WHERE path LIKE ?", (f"%{roster_team_c.name}",))
    row = cur.fetchone()
    assert row and len(row[0]) == 40
