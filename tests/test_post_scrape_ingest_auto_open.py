"""Test auto-open Ingestion Lab trigger when new HTML ingested and no rules exist (Milestone 7.10.61)."""
from __future__ import annotations

import sqlite3
from pathlib import Path

from gui.services.service_locator import services
from gui.services.event_bus import EventBus
from gui.services.post_scrape_ingest import PostScrapeIngestionHook


class _FakeSignal:
    def __init__(self):
        self._handlers = []
    def connect(self, fn):
        self._handlers.append(fn)
    def emit(self, payload):
        for h in list(self._handlers):
            h(payload)

class _FakeRunner:
    def __init__(self):
        self.scrape_finished = _FakeSignal()


def _schema(conn: sqlite3.Connection):
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


def test_auto_open_ingestion_lab_event_emitted(tmp_path: Path):
    # Prepare HTML assets (division prefix naming)
    data_dir = tmp_path / "1_SampleDiv"
    data_dir.mkdir()
    (data_dir / "ranking_table_1_SampleDiv.html").write_text("<html><table></table></html>", encoding="utf-8")
    (data_dir / "team_roster_1_SampleDiv_Team_A_001.html").write_text("<html>RosterA</html>", encoding="utf-8")

    bus = EventBus()
    services.register("event_bus", bus, allow_override=True)
    conn = sqlite3.connect(":memory:")
    _schema(conn)
    services.register("sqlite_conn", conn, allow_override=True)
    # Intentionally do NOT register rule_version_store -> simulate no rules scenario

    received_auto = []
    bus.subscribe("OPEN_INGESTION_LAB", lambda evt: received_auto.append(evt.payload))

    runner = _FakeRunner()
    PostScrapeIngestionHook(runner, lambda: str(data_dir))
    runner.scrape_finished.emit({"ok": True})

    assert received_auto, "Expected OPEN_INGESTION_LAB event when no rules exist and new HTML ingested"
    assert received_auto[0]["reason"] == "auto_open_first_html"


def test_no_auto_open_when_rules_exist(tmp_path: Path):
    data_dir = tmp_path / "1_SampleDiv2"
    data_dir.mkdir()
    (data_dir / "ranking_table_1_SampleDiv2.html").write_text("<html></html>", encoding="utf-8")

    bus = EventBus()
    services.register("event_bus", bus, allow_override=True)
    conn = sqlite3.connect(":memory:")
    _schema(conn)
    services.register("sqlite_conn", conn, allow_override=True)

    # Simulated rule store with latest_version attribute
    class _RuleStore:
        latest_version = 3
    services.register("rule_version_store", _RuleStore(), allow_override=True)

    received_auto = []
    bus.subscribe("OPEN_INGESTION_LAB", lambda evt: received_auto.append(evt.payload))

    runner = _FakeRunner()
    PostScrapeIngestionHook(runner, lambda: str(data_dir))
    runner.scrape_finished.emit({"ok": True})

    assert not received_auto, "Did not expect auto-open event when rules already exist"
