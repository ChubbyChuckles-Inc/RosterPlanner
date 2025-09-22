"""Ingest-only CLI (Milestone 5.9.21)

Provides a fast path to ingest already-scraped HTML assets residing in a
directory into a SQLite database without performing a fresh scrape.

Features:
 - Auto-creates the minimal *singular* schema tables if they do not yet exist.
 - Runs the `IngestionCoordinator` over the provided data directory.
 - Emits either human-readable summary or JSON (via `--json`).
 - Includes post-ingest consistency validation result (errors, stats).
 - Exit code 0 when ingest + validation are clean, else 1.

Example:
  roster-ingest --data-dir ./data --db ingest.sqlite --json
"""

from __future__ import annotations

import argparse
import json
import os
import sqlite3
import sys
from typing import Any, Dict

from gui.services.ingestion_coordinator import IngestionCoordinator
from gui.services.consistency_validation_service import ConsistencyValidationService


SCHEMA_SQL = """
CREATE TABLE IF NOT EXISTS division(
  division_id INTEGER PRIMARY KEY,
  name TEXT,
  season INTEGER,
  level TEXT,
  category TEXT
);
CREATE TABLE IF NOT EXISTS team(
  team_id INTEGER PRIMARY KEY,
  club_id INTEGER,
  division_id INTEGER,
  name TEXT
);
CREATE TABLE IF NOT EXISTS club(
  club_id INTEGER PRIMARY KEY,
  name TEXT
);
CREATE TABLE IF NOT EXISTS player(
  player_id INTEGER PRIMARY KEY,
  team_id INTEGER,
  full_name TEXT,
  live_pz INTEGER
);
-- Optional ranking table (created by coordinator if missing but harmless here)
CREATE TABLE IF NOT EXISTS division_ranking(
  division_id INTEGER,
  position INTEGER,
  team_name TEXT,
  points INTEGER,
  matches_played INTEGER,
  wins INTEGER,
  draws INTEGER,
  losses INTEGER,
  PRIMARY KEY(division_id, position)
);
"""


def _ensure_schema(conn: sqlite3.Connection) -> None:
    conn.executescript(SCHEMA_SQL)
    # Auxiliary tables the coordinator expects / maintains
    conn.executescript(
        """
        CREATE TABLE IF NOT EXISTS id_map(
            entity_type TEXT,
            source_key TEXT,
            assigned_id INTEGER PRIMARY KEY AUTOINCREMENT,
            UNIQUE(entity_type, source_key)
        );
        CREATE TABLE IF NOT EXISTS provenance(
            path TEXT PRIMARY KEY,
            sha1 TEXT NOT NULL,
            last_ingested_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            parser_version INTEGER DEFAULT 1
        );
        CREATE TABLE IF NOT EXISTS provenance_summary(
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            ingested_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            divisions INTEGER,
            teams INTEGER,
            players INTEGER,
            files_processed INTEGER,
            files_skipped INTEGER
        );
        """
    )


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    p = argparse.ArgumentParser(description="Ingest existing scraped HTML assets into SQLite")
    p.add_argument(
        "--data-dir",
        required=True,
        help="Directory containing ranking_table_*.html and team_roster_*.html files",
    )
    p.add_argument(
        "--db",
        default=":memory:",
        help="SQLite database file path (default: in-memory). If a file path is provided it will be created if missing.",
    )
    p.add_argument("--season", type=int, default=2025, help="Season year tag (stored in division)")
    p.add_argument("--json", action="store_true", help="Emit JSON instead of human-readable text")
    return p.parse_args(argv)


def _summary_to_dict(summary: IngestionCoordinator.IngestionSummary | Any) -> Dict[str, Any]:  # type: ignore
    # The summary is a dataclass; access attributes directly.
    return {
        "divisions_ingested": getattr(summary, "divisions_ingested", 0),
        "teams_ingested": getattr(summary, "teams_ingested", 0),
        "players_ingested": getattr(summary, "players_ingested", 0),
        "skipped_files": getattr(summary, "skipped_files", 0),
        "processed_files": getattr(summary, "processed_files", 0),
        "errors": [getattr(e, "__dict__", {}) for e in getattr(summary, "errors", [])],
    }


def run_ingest(data_dir: str, db_path: str) -> tuple[Dict[str, Any], Dict[str, Any]]:
    if db_path != ":memory":
        os.makedirs(os.path.dirname(os.path.abspath(db_path)) or ".", exist_ok=True)
    conn = sqlite3.connect(db_path)
    _ensure_schema(conn)
    coord = IngestionCoordinator(base_dir=data_dir, conn=conn)
    summary = coord.run()
    # Coordinator already runs validation but we rerun to capture freshly for output
    validation = ConsistencyValidationService.run_and_register(conn)
    return _summary_to_dict(summary), {
        "errors": validation.errors,
        "warnings": validation.warnings,
        "stats": validation.stats,
        "clean": validation.is_clean(),
    }


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    data_dir = args.data_dir
    if not os.path.isdir(data_dir):
        print(f"Data directory not found: {data_dir}", file=sys.stderr)
        return 2
    summary_dict, validation_dict = run_ingest(data_dir, args.db)
    exit_code = 0
    if summary_dict.get("errors") or not validation_dict.get("clean", True):
        exit_code = 1
    if args.json:
        payload = {"summary": summary_dict, "consistency": validation_dict}
        print(json.dumps(payload, ensure_ascii=False, indent=2))
    else:
        print("Ingestion Summary:")
        print(f"  Divisions: {summary_dict['divisions_ingested']}")
        print(f"  Teams: {summary_dict['teams_ingested']}")
        print(f"  Players: {summary_dict['players_ingested']}")
        print(f"  Files processed: {summary_dict['processed_files']}")
        print(f"  Files skipped: {summary_dict['skipped_files']}")
        if summary_dict["errors"]:
            print(f"  Ingest Errors: {len(summary_dict['errors'])}")
            for e in summary_dict["errors"][:5]:  # show first few
                print(f"    - {e.get('division')}: {e.get('message')}")
        status = "CLEAN" if validation_dict["clean"] else "ERRORS"
        stats = ", ".join(f"{k}={v}" for k, v in validation_dict["stats"].items())
        print(f"Consistency: {status} ({stats})")
        if not validation_dict["clean"]:
            for err in validation_dict["errors"]:
                print(f"  ! {err}")
    return exit_code


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
