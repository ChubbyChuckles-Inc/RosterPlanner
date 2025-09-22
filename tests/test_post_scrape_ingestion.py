"""Integration test for Milestone 5.9.5 (post-scrape automatic ingestion).

This test simulates the sequence:
 1. Prepare a temporary data directory with ranking + roster HTML files.
 2. Register an EventBus and in-memory sqlite connection (with minimal schema) in the service locator.
 3. Instantiate a fake scrape runner and PostScrapeIngestionHook.
 4. Emit the scrape_finished signal.
 5. Assert that divisions/teams were ingested and both DATA_REFRESHED and DATA_REFRESH_COMPLETED events fired.

We avoid real PyQt ScrapeRunner / signals to keep the test Qt-agnostic.
"""

from __future__ import annotations

from pathlib import Path
import sqlite3
import textwrap

from gui.services.service_locator import services
from gui.services.event_bus import EventBus, GUIEvent
from gui.services.post_scrape_ingest import PostScrapeIngestionHook


class _FakeSignal:
    def __init__(self):
        self._handlers = []

    def connect(self, fn):  # noqa: D401 - simple signal mimic
        self._handlers.append(fn)

    def emit(self, payload):
        for h in list(self._handlers):
            h(payload)


class _FakeRunner:
    def __init__(self):
        self.scrape_finished = _FakeSignal()


def _create_minimal_gui_ingest_schema(conn: sqlite3.Connection):
    # Minimal tables required by IngestionCoordinator & repositories
    conn.executescript(
        """
        CREATE TABLE IF NOT EXISTS divisions(
            id TEXT PRIMARY KEY,
            name TEXT,
            level TEXT,
            category TEXT
        );
        CREATE TABLE IF NOT EXISTS clubs(
            id TEXT PRIMARY KEY,
            name TEXT
        );
        CREATE TABLE IF NOT EXISTS teams(
            id TEXT PRIMARY KEY,
            name TEXT,
            division_id TEXT,
            club_id TEXT
        );
        """
    )
    conn.commit()


def test_post_scrape_ingestion_triggers_ingest_and_events(tmp_path):
    # 1. Create sample HTML assets
    data_dir = tmp_path / "data"
    data_dir.mkdir()
    # Ranking table
    (data_dir / "ranking_table_1_Bezirksliga_Erwachsene.html").write_text(
        "<html><body>Rank</body></html>", encoding="utf-8"
    )
    # Two team rosters (naming pattern as expected by DataAuditService)
    (data_dir / "team_roster_1_Bezirksliga_Erwachsene_SV_Groitzsch_1861_129200.html").write_text(
        "<html><body>Roster A</body></html>", encoding="utf-8"
    )
    (data_dir / "team_roster_1_Bezirksliga_Erwachsene_SV_Arzberg_129095.html").write_text(
        "<html><body>Roster B</body></html>", encoding="utf-8"
    )

    # 2. Register services
    bus = EventBus()
    services.register("event_bus", bus, allow_override=True)
    conn = sqlite3.connect(":memory:")
    _create_minimal_gui_ingest_schema(conn)
    services.register("sqlite_conn", conn, allow_override=True)

    # Capture events
    received_refresh = []
    received_completed = []

    def _on_refreshed(evt):  # evt.payload holds {summary}
        received_refresh.append(evt.payload)

    def _on_completed(evt):  # evt.payload holds {ingestion: summary}
        received_completed.append(evt.payload)

    bus.subscribe("DATA_REFRESHED", _on_refreshed)
    bus.subscribe(GUIEvent.DATA_REFRESH_COMPLETED, _on_completed)

    # 3. Hook installation with fake runner
    runner = _FakeRunner()
    PostScrapeIngestionHook(runner, lambda: str(data_dir))

    # 4. Emit scrape_finished
    runner.scrape_finished.emit({"ok": True})

    # 5. Assertions
    # Divisions & teams ingested
    cur = conn.execute("SELECT COUNT(*) FROM divisions")
    assert cur.fetchone()[0] == 1  # one division
    cur = conn.execute("SELECT COUNT(*) FROM teams")
    assert cur.fetchone()[0] == 2  # two teams

    # Events fired
    assert received_refresh, "Expected DATA_REFRESHED event"
    assert received_completed, "Expected DATA_REFRESH_COMPLETED event"

    # Summary payload structure sanity
    summary = received_completed[0]["ingestion"]
    assert summary.teams_ingested == 2
    assert summary.divisions_ingested == 1
    # processed_files should be >= roster count (ranking + 2 rosters) minus any skipped
    assert summary.processed_files >= 2
