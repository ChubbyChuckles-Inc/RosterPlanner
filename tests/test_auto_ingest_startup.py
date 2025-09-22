import os
import sqlite3
from PyQt6.QtCore import QCoreApplication

from gui.services.service_locator import services
from gui.workers import LandingLoadWorker
from config import settings

# Helper to run Qt thread synchronously in test


def run_worker(worker_cls, *args, **kwargs):
    app = QCoreApplication.instance() or QCoreApplication([])
    result_container = {}
    w = worker_cls(*args, **kwargs)

    def _finished(teams, error):
        result_container["teams"] = teams
        result_container["error"] = error
        app.quit()

    w.finished.connect(_finished)  # type: ignore
    w.start()
    app.exec()  # run event loop until worker finishes
    return result_container["teams"], result_container["error"]


def test_auto_ingest_populates_from_existing_assets(tmp_path, monkeypatch):
    # Build fake data dir with minimal HTML assets
    data_dir = tmp_path / "data"
    os.makedirs(data_dir, exist_ok=True)
    # Minimal division folder with ranking_table and roster file
    div_dir = data_dir / "1_Stadtliga_Gruppe_1"
    os.makedirs(div_dir, exist_ok=True)
    (div_dir / "ranking_table_1_Stadtliga_Gruppe_1.html").write_text(
        "<html></html>", encoding="utf-8"
    )
    # Use a simple team name pattern so DataAuditService can reconstruct division & team name
    (div_dir / "team_roster_1_Stadtliga_Gruppe_1_Fuechse_A_5000.html").write_text(
        "<html></html>", encoding="utf-8"
    )

    # Point settings.DATA_DIR to our temp
    monkeypatch.setattr(settings, "DATA_DIR", str(data_dir))

    # Create in-memory sqlite DB and register connection
    conn = sqlite3.connect(":memory:", check_same_thread=False)
    # Create minimal schema required by ingestion coordinator & DataStateService
    conn.executescript(
        """
    CREATE TABLE divisions(id TEXT PRIMARY KEY, name TEXT, level TEXT, category TEXT);
    CREATE TABLE clubs(id TEXT PRIMARY KEY, name TEXT);
    CREATE TABLE teams(id TEXT PRIMARY KEY, name TEXT, division_id TEXT, club_id TEXT);
    """
    )
    services.register("sqlite_conn", conn, allow_override=True)
    # No provenance table yet (ingestion will create it)

    teams, error = run_worker(LandingLoadWorker, club_id=9999, season=2025)
    assert error == ""
    # Auto-ingest should have discovered at least one team
    assert len(teams) == 1, "Expected auto-ingest to populate one team from existing HTML assets"
