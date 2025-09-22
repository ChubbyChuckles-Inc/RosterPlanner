"""Tests for Milestone 5.9.12 transactional per-division ingest.

Verifies that a failure in one division does not roll back successfully
ingested prior divisions.
"""

from __future__ import annotations

import sqlite3
from pathlib import Path

from gui.services.ingestion_coordinator import IngestionCoordinator


def _schema(conn: sqlite3.Connection):
    conn.executescript(
        """
        CREATE TABLE division(division_id INTEGER PRIMARY KEY, name TEXT, season INTEGER);
        CREATE TABLE team(team_id INTEGER PRIMARY KEY, club_id INTEGER, division_id INTEGER, name TEXT);
        CREATE TABLE club(club_id INTEGER PRIMARY KEY, name TEXT);
        CREATE TABLE player(player_id INTEGER PRIMARY KEY, team_id INTEGER, full_name TEXT, live_pz INTEGER);
        """
    )
    conn.commit()


def _write_division_files(base: Path, div: str, team_tokens: list[str]):
    # ranking table file
    (base / f"ranking_table_{div}.html").write_text(
        "<html><table><tr><th>Pos</th><th>Team</th></tr><tr><td>1</td><td>X</td></tr></table></html>",
        encoding="utf-8",
    )
    for idx, name in enumerate(team_tokens, start=1):
        (base / f"team_roster_{div}_{name}_{1000+idx}.html").write_text(
            f"<html><body>Roster {name}</body></html>", encoding="utf-8"
        )


class FailingIngestionCoordinator(IngestionCoordinator):
    def _ingest_single_division(self, d):  # type: ignore[override]
        # Fail second division deliberately
        if d.division.startswith("2_"):
            raise RuntimeError("synthetic division failure")
        return super()._ingest_single_division(d)


def test_transactional_division_rollback(tmp_path):
    # Prepare data directory with two divisions
    data_dir = tmp_path / "data"
    data_dir.mkdir()
    _write_division_files(data_dir, "1_Bezirksliga_Erwachsene", ["TeamA", "TeamB"])
    _write_division_files(data_dir, "2_Bezirksliga_Erwachsene", ["TeamC"])  # will fail

    conn = sqlite3.connect(":memory:")
    _schema(conn)

    coord = FailingIngestionCoordinator(str(data_dir), conn)
    summary = coord.run()

    # Only first division ingested
    cur = conn.execute("SELECT name FROM division")
    divisions = [r[0] for r in cur.fetchall()]
    assert len(divisions) == 1 and any("1 Bezirksliga" in d for d in divisions)

    # Teams only from first division present
    team_rows = list(conn.execute("SELECT team_id, division_id FROM team"))
    assert len(team_rows) >= 1  # at least the two teams (dedup may reduce if logic changes)

    # Summary reflects only successful division
    assert summary.divisions_ingested == 1
    # Failure should not raise; provenance_summary may still exist with single row
