"""Tests Milestone 5.9.13 ingest error channel.

Ensures that a division-level failure is:
 - Rolled back (handled already by transactional test)
 - Captured in IngestionSummary.errors
 - Persisted to ingest_error table
 - Published via EventBus as INGEST_ERROR
"""

from __future__ import annotations

import sqlite3
from pathlib import Path

from gui.services.ingestion_coordinator import IngestionCoordinator
from gui.services.event_bus import EventBus


def _schema(conn: sqlite3.Connection):
    conn.executescript(
        """
        CREATE TABLE division(division_id INTEGER PRIMARY KEY, name TEXT, season INTEGER);
        CREATE TABLE team(team_id INTEGER PRIMARY KEY, club_id INTEGER, division_id INTEGER, name TEXT);
        CREATE TABLE club(club_id INTEGER PRIMARY KEY, name TEXT);
        CREATE TABLE player(player_id INTEGER PRIMARY KEY, team_id INTEGER, full_name TEXT, live_pz INTEGER);
        CREATE TABLE division_ranking(division_id INTEGER, payload TEXT);
        """
    )
    conn.commit()


def _write_division_files(base: Path, div: str, team_tokens: list[str]):
    (base / f"ranking_table_{div}.html").write_text(
        "<html><table><tr><th>Pos</th><th>Team</th></tr><tr><td>1</td><td>X</td></tr></table></html>",
        encoding="utf-8",
    )
    for idx, name in enumerate(team_tokens, start=1):
        (base / f"team_roster_{div}_{name}_{1000+idx}.html").write_text(
            f"<html><body>Roster {name}</body></html>", encoding="utf-8"
        )


class FailingDivisionCoordinator(IngestionCoordinator):
    def _ingest_single_division(self, d):  # type: ignore[override]
        if d.division.startswith("2_"):
            raise RuntimeError("synthetic parser failure")
        return super()._ingest_single_division(d)


def test_ingest_error_channel_publishes_and_persists(tmp_path):
    data_dir = tmp_path / "data"
    data_dir.mkdir()
    _write_division_files(data_dir, "1_Bezirksliga_Erwachsene", ["TeamA"])  # success
    _write_division_files(data_dir, "2_Bezirksliga_Erwachsene", ["TeamB"])  # fail

    conn = sqlite3.connect(":memory:")
    _schema(conn)
    bus = EventBus()
    captured = []

    bus.subscribe("INGEST_ERROR", lambda evt: captured.append(evt))

    coord = FailingDivisionCoordinator(str(data_dir), conn, bus)
    summary = coord.run()

    # Summary contains one error
    assert len(summary.errors) == 1
    err = summary.errors[0]
    assert "2_Bezirksliga" in err.division
    assert err.severity == "error"
    # Event captured
    assert captured and "synthetic parser failure" in captured[0].payload["message"]
    # Persisted in table
    rows = list(conn.execute("SELECT division, message, severity FROM ingest_error"))
    assert rows and rows[0][2] == "error"
