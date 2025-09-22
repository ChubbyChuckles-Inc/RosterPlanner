"""Performance baseline test for Milestone 5.9.18.

Measures end-to-end ingestion time over a representative sample of the
existing scraped HTML assets. The goal is to ensure the current pipeline
completes under an initial baseline threshold so future regressions can
be detected.

Rationale:
 - We use a subset of the repository's `data` directory (one or more
   division folders) to avoid excessive test runtime in CI while still
   exercising ranking + roster parsing paths.
 - The test records the wall-clock duration (perf_counter) for a fresh
   in-memory SQLite database ingest run.
 - A soft threshold (e.g. 2.0 seconds) is asserted; if the environment
   is notably slower (e.g. under heavy load) we allow a small margin by
   marking the test xfail via environment override (INGEST_PERF_RELAX=1).

If this test becomes flaky on slower machines, adjust the THRESHOLD or
split into tiered benchmarks. For now a single assertion provides an
early warning signal.
"""

from __future__ import annotations

import os
import sqlite3
import time
from pathlib import Path

import pytest

from gui.services.ingestion_coordinator import IngestionCoordinator

# Threshold in seconds for baseline ingest (tunable). Initial observed
# runtime on reference dev machine ~9.3s (includes HTML parsing overhead
# for multiple divisions). We start with a conservative 12s ceiling to
# avoid flaky failures; future optimizations should lower this value.
THRESHOLD_SECONDS = 12.0

# Allow relax (skip hard failure) when env var set (e.g. CI under load)
RELAX_ENV = "INGEST_PERF_RELAX"


@pytest.mark.performance
def test_ingestion_performance_baseline(tmp_path):
    # 1. Collect representative HTML assets (single division to keep test fast).
    repo_data_root = Path("data")
    assert repo_data_root.exists(), "Expected repository data directory with sample HTML"
    # Select the first division folder only to constrain runtime.
    division_dirs = [p for p in repo_data_root.iterdir() if p.is_dir()][:1]
    target_data_dir = tmp_path / "data"
    target_data_dir.mkdir()
    copied_files = 0
    for d in division_dirs:
        # Copy only ranking table + up to first 8 roster files to reduce variance.
        roster_count = 0
        for f in sorted(d.iterdir()):
            if not f.is_file():
                continue
            if f.name.startswith("ranking_table_"):
                dest = target_data_dir / f.name
                dest.write_text(f.read_text(encoding="utf-8", errors="ignore"), encoding="utf-8")
                copied_files += 1
            elif f.name.startswith("team_roster_") and roster_count < 8:
                dest = target_data_dir / f.name
                dest.write_text(f.read_text(encoding="utf-8", errors="ignore"), encoding="utf-8")
                copied_files += 1
                roster_count += 1
    # Safety: ensure we actually copied something
    assert copied_files > 0, "No HTML fixtures copied for performance test"

    # 2. Initialize minimal singular schema (mirrors ingestion singular tables subset)
    conn = sqlite3.connect(":memory:")
    conn.executescript(
        """
        CREATE TABLE division(division_id INTEGER PRIMARY KEY, name TEXT, season INTEGER, level TEXT, category TEXT);
        CREATE TABLE team(team_id INTEGER PRIMARY KEY, club_id INTEGER, division_id INTEGER, name TEXT);
        CREATE TABLE club(club_id INTEGER PRIMARY KEY, name TEXT);
        CREATE TABLE player(player_id INTEGER PRIMARY KEY, team_id INTEGER, full_name TEXT, live_pz INTEGER);
        CREATE TABLE division_ranking(division_id INTEGER, position INTEGER, team_name TEXT, points INTEGER, matches_played INTEGER, wins INTEGER, draws INTEGER, losses INTEGER, PRIMARY KEY(division_id, position));
        CREATE TABLE id_map(entity_type TEXT, source_key TEXT, assigned_id INTEGER PRIMARY KEY AUTOINCREMENT, UNIQUE(entity_type, source_key));
        CREATE TABLE provenance(path TEXT PRIMARY KEY, sha1 TEXT NOT NULL, last_ingested_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP, parser_version INTEGER DEFAULT 1);
        CREATE TABLE provenance_summary(id INTEGER PRIMARY KEY AUTOINCREMENT, ingested_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP, divisions INTEGER, teams INTEGER, players INTEGER, files_processed INTEGER, files_skipped INTEGER);
        """
    )

    # 3. Execute ingestion and measure wall-clock duration
    coord = IngestionCoordinator(str(target_data_dir), conn)
    start = time.perf_counter()
    summary = coord.run()
    duration = time.perf_counter() - start

    # Sanity checks (non-zero entities)
    assert summary.divisions_ingested > 0
    assert summary.teams_ingested > 0

    # 4. Performance assertion
    relax = os.environ.get(RELAX_ENV) == "1"
    if duration > THRESHOLD_SECONDS:
        msg = f"Ingestion exceeded baseline: {duration:.3f}s > {THRESHOLD_SECONDS:.2f}s"
        if relax:
            pytest.xfail(msg)
        else:
            pytest.fail(msg)

    # Optional: emit timing for CI logs
    print(f"[PERF] Ingestion duration: {duration:.3f}s (threshold {THRESHOLD_SECONDS:.2f}s)")
