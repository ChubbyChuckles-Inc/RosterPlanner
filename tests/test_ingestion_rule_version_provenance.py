"""Test that IngestionCoordinator records active rule_version in provenance (Milestone 7.10.60)."""

from __future__ import annotations

import sqlite3
from pathlib import Path

from gui.services.ingestion_coordinator import IngestionCoordinator
from gui.services.service_locator import services


def _create_minimal_schema(conn: sqlite3.Connection):
    # Create singular-mode tables matching IngestionCoordinator defaults
    conn.executescript(
        """
        CREATE TABLE IF NOT EXISTS division(division_id TEXT PRIMARY KEY, name TEXT, season TEXT);
        CREATE TABLE IF NOT EXISTS club(club_id TEXT PRIMARY KEY, name TEXT);
        CREATE TABLE IF NOT EXISTS team(team_id TEXT PRIMARY KEY, club_id TEXT, division_id TEXT, name TEXT, canonical_name TEXT);
        CREATE TABLE IF NOT EXISTS player(player_id TEXT PRIMARY KEY, team_id TEXT, name TEXT);
        CREATE TABLE IF NOT EXISTS division_ranking(division_id TEXT, team_name TEXT, points INTEGER, diff INTEGER);
        """
    )
    conn.commit()


def test_provenance_includes_rule_version(tmp_path: Path, monkeypatch):
    # Arrange: create minimal HTML structure consistent with audit expectations
    div_dir = tmp_path / "1_TestDivision"
    div_dir.mkdir()
    # ranking table (optional) - keep minimal placeholder
    (div_dir / "ranking_table_1_TestDivision.html").write_text(
        "<html><table class='rank'><tr><th>A</th></tr><tr><td>1</td></tr></table></html>",
        encoding="utf-8",
    )
    # One team roster file (naming consistent with existing heuristics)
    (div_dir / "team_roster_1_TestDivision_Demo_Team_123.html").write_text(
        "<html><div class='player'>P1</div></html>", encoding="utf-8"
    )
    conn = sqlite3.connect(":memory:")
    _create_minimal_schema(conn)
    coord = IngestionCoordinator(str(tmp_path), conn)
    # Simulate published active rule version via service locator
    services.register("active_rule_version", 42, allow_override=True)
    summary = coord.run()
    assert summary.divisions_ingested >= 1
    # Query provenance rows and ensure rule_version column populated
    rows = conn.execute("SELECT path, rule_version FROM provenance").fetchall()
    assert rows, "expected at least one provenance row"
    # All rows should have rule_version 42
    assert all(r[1] == 42 for r in rows), rows


def test_provenance_rule_version_nullable_when_absent(tmp_path: Path):
    div_dir = tmp_path / "1_OtherDivision"
    div_dir.mkdir()
    (div_dir / "ranking_table_1_OtherDivision.html").write_text(
        "<html><table><tr><th>X</th></tr><tr><td>5</td></tr></table></html>",
        encoding="utf-8",
    )
    conn = sqlite3.connect(":memory:")
    _create_minimal_schema(conn)
    # Ensure prior test registration does not leak
    try:
        services.unregister("active_rule_version")  # type: ignore[attr-defined]
    except Exception:
        pass
    coord = IngestionCoordinator(str(tmp_path), conn)
    coord.active_rule_version = None
    coord.run()
    rows = conn.execute("SELECT path, rule_version FROM provenance").fetchall()
    assert rows
    # All rows should have NULL (None) rule_version since no active version published
    assert all(r[1] is None for r in rows), rows
