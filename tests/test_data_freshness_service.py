import json
import sqlite3
from datetime import datetime, timedelta
from pathlib import Path

from gui.services.data_freshness_service import DataFreshnessService, humanize_age
from typing import Optional


def _setup_tracking(tmp_path: Path, last_scrape: Optional[datetime]):
    payload = {"last_scrape": last_scrape.isoformat() if last_scrape else None, "divisions": {}}
    (tmp_path / "match_tracking.json").write_text(json.dumps(payload), encoding="utf-8")


def _setup_db(
    with_summary: bool = True, with_provenance: bool = True, ingest_ts: str = "2025-01-02 03:04:05"
):
    conn = sqlite3.connect(":memory:")
    if with_summary:
        conn.execute(
            "CREATE TABLE provenance_summary(id INTEGER PRIMARY KEY, ingested_at TEXT, divisions INTEGER, teams INTEGER, players INTEGER, files_processed INTEGER, files_skipped INTEGER)"
        )
        conn.execute(
            "INSERT INTO provenance_summary(ingested_at, divisions, teams, players, files_processed, files_skipped) VALUES(?,?,?,?,?,?)",
            (ingest_ts, 1, 1, 0, 2, 0),
        )
    if with_provenance:
        conn.execute(
            "CREATE TABLE provenance(path TEXT PRIMARY KEY, sha1 TEXT, last_ingested_at TEXT)"
        )
        conn.execute(
            "INSERT OR REPLACE INTO provenance(path, sha1, last_ingested_at) VALUES(?,?,?)",
            ("file_a", "abc", ingest_ts),
        )
    conn.commit()
    return conn


def test_data_freshness_with_summary(tmp_path):
    last_scrape = datetime.utcnow() - timedelta(hours=2, minutes=5)
    _setup_tracking(tmp_path, last_scrape)
    conn = _setup_db(with_summary=True, with_provenance=True)
    svc = DataFreshnessService(base_dir=str(tmp_path), conn=conn)
    snap = svc.current()
    assert snap.last_scrape is not None
    assert snap.last_ingest is not None
    assert (
        snap.age_since_scrape_seconds is not None and snap.age_since_scrape_seconds > 7200 - 70
    )  # allow small clock drift
    assert "Scrape:" in snap.human_summary()


def test_data_freshness_fallback_to_provenance(tmp_path):
    # No summary table -> should still pick provenance
    last_scrape = datetime.utcnow() - timedelta(minutes=10)
    _setup_tracking(tmp_path, last_scrape)
    conn = _setup_db(with_summary=False, with_provenance=True, ingest_ts="2025-01-02 03:04:05")
    svc = DataFreshnessService(base_dir=str(tmp_path), conn=conn)
    snap = svc.current()
    assert snap.last_ingest is not None
    assert snap.last_ingest.year == 2025


def test_humanize_age_formatting():
    assert humanize_age(5).endswith("s ago")
    assert humanize_age(65).endswith("m ago") or humanize_age(65).startswith("1m")
    assert humanize_age(3600).startswith("1h")
    assert humanize_age(90000).endswith("d ago")
