"""Ingestion Pipeline (Milestone 3.3)

Transforms scraped HTML assets into normalized SQLite rows.

Scope (initial increment):
 - Discover ranking_table_*.html files under a provided root directory.
 - For each ranking table, parse division + team roster link hints using existing parsing utilities.
 - Discover matching team_roster_*.html files for each division/team.
 - Parse players (live_pz) from roster pages (roster_parser.extract_players) and prepare upsert operations.
 - Idempotent upsert: insert new rows or update changed attributes (player live_pz) while keeping stable primary keys.
 - HTML hashing (Milestone 3.3.1) to skip unchanged files prior to parsing.
 - Provenance recording (Milestone 3.3.2) storing source_file, parser_version, hash.

Design Notes:
 - For simplicity, we derive natural keys: division(name+season placeholder), team(name+division), player(name+team).
 - Future enhancements: stable numeric IDs from upstream site once available; season extracted from filename/path.
 - We wrap per-file ingestion in its own transaction for partial resilience; caller may opt for outer transaction.

Public API (initial):
 - ingest_path(conn, root_path: str, parser_version: str = "v1") -> IngestReport
 - hash_html(content: str) -> str

The function returns a dataclass report with counts of inserted/updated/skipped entities and skipped files by hash.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
import hashlib
import sqlite3
from typing import Dict, List, Tuple

from parsing.ranking_parser import parse_ranking_table
from parsing.roster_parser import extract_players


PARSER_VERSION_DEFAULT = "v1"


def hash_html(content: str) -> str:
    """Return SHA256 hex digest of raw HTML content."""
    return hashlib.sha256(content.encode("utf-8")).hexdigest()


@dataclass
class FileIngestResult:
    source_file: str
    hash: str
    skipped_unchanged: bool
    inserted_players: int = 0
    updated_players: int = 0


@dataclass
class IngestReport:
    files: List[FileIngestResult] = field(default_factory=list)

    @property
    def total_players_inserted(self) -> int:
        return sum(f.inserted_players for f in self.files)

    @property
    def total_players_updated(self) -> int:
        return sum(f.updated_players for f in self.files)

    @property
    def files_skipped(self) -> int:
        return sum(1 for f in self.files if f.skipped_unchanged)


def _provenance_exists(conn: sqlite3.Connection, source_file: str, file_hash: str) -> bool:
    cur = conn.cursor()
    cur.execute(
        "SELECT 1 FROM ingest_provenance WHERE source_file=? AND hash=?",
        (source_file, file_hash),
    )
    return cur.fetchone() is not None


def _record_provenance(
    conn: sqlite3.Connection, source_file: str, parser_version: str, file_hash: str
) -> None:
    conn.execute(
        "INSERT OR IGNORE INTO ingest_provenance(source_file, parser_version, hash) VALUES (?,?,?)",
        (source_file, parser_version, file_hash),
    )


def _upsert_division(conn: sqlite3.Connection, name: str) -> int:
    cur = conn.cursor()
    # season placeholder: 0 until season extraction implemented
    cur.execute(
        "INSERT INTO division(name, season) VALUES(?, 0) ON CONFLICT(name, season) DO NOTHING",
        (name,),
    )
    cur.execute("SELECT division_id FROM division WHERE name=? AND season=0", (name,))
    return int(cur.fetchone()[0])


def _upsert_team(conn: sqlite3.Connection, division_id: int, name: str) -> int:
    cur = conn.cursor()
    cur.execute(
        "INSERT INTO team(division_id, club_id, name) VALUES(?, NULL, ?) ON CONFLICT(division_id, name) DO NOTHING",
        (division_id, name),
    )
    cur.execute(
        "SELECT team_id FROM team WHERE division_id=? AND name=?",
        (division_id, name),
    )
    return int(cur.fetchone()[0])


def _upsert_player(
    conn: sqlite3.Connection, team_id: int, name: str, live_pz: int | None
) -> Tuple[bool, bool]:
    """Return (inserted, updated). Updates when existing row has different live_pz."""
    cur = conn.cursor()
    cur.execute(
        "SELECT player_id, live_pz FROM player WHERE team_id=? AND full_name=?",
        (team_id, name),
    )
    row = cur.fetchone()
    if not row:
        cur.execute(
            "INSERT INTO player(team_id, full_name, live_pz) VALUES(?,?,?)",
            (team_id, name, live_pz),
        )
        return True, False
    player_id, existing_pz = row
    if existing_pz != live_pz:
        cur.execute(
            "UPDATE player SET live_pz=? WHERE player_id=?",
            (live_pz, player_id),
        )
        return False, True
    return False, False


def ingest_path(
    conn: sqlite3.Connection, root_path: str | Path, parser_version: str = PARSER_VERSION_DEFAULT
) -> IngestReport:
    """Ingest all recognized HTML assets beneath root_path.

    Current recognition:
      - ranking_table_*.html -> parse division + team roster link text (team names)
      - team_roster_*.html -> parse players (live_pz)

    Hash skipping: if (source_file, hash) already present in ingest_provenance we skip parsing & upsert entirely.
    """
    root = Path(root_path)
    report = IngestReport()
    ranking_files = list(root.rglob("ranking_table_*.html"))
    roster_files = {p.name: p for p in root.rglob("team_roster_*.html")}

    for ranking in ranking_files:
        content = ranking.read_text(encoding="utf-8", errors="ignore")
        file_hash = hash_html(content)
        result = FileIngestResult(source_file=str(ranking), hash=file_hash, skipped_unchanged=False)
        if _provenance_exists(conn, str(ranking), file_hash):
            result.skipped_unchanged = True
            report.files.append(result)
            continue
        # Parse division + teams
        division_name, team_entries = parse_ranking_table(content, source_hint=ranking.name)
        with conn:  # per file transaction
            div_id = _upsert_division(conn, division_name)
            for t in team_entries:
                team_name = t.get("team_name")
                if not team_name:
                    continue
                team_id = _upsert_team(conn, div_id, team_name)
                # Attempt roster file resolution by normalized name presence in filename
                # (Simplified heuristic; future: link-based mapping)
                for fname, roster_path in roster_files.items():
                    if team_name.replace(" ", "_") in fname:
                        roster_html = roster_path.read_text(encoding="utf-8", errors="ignore")
                        roster_hash = hash_html(roster_html)
                        if _provenance_exists(conn, str(roster_path), roster_hash):
                            continue
                        players = extract_players(roster_html, team_id=str(team_id))
                        inserted = updated = 0
                        for p in players:
                            ins, upd = _upsert_player(conn, team_id, p.name, p.live_pz)
                            if ins:
                                inserted += 1
                            if upd:
                                updated += 1
                        if players:
                            result.inserted_players += inserted
                            result.updated_players += updated
                        _record_provenance(conn, str(roster_path), parser_version, roster_hash)
            # Record provenance for ranking file after successful ingestion
            _record_provenance(conn, str(ranking), parser_version, file_hash)
        report.files.append(result)
    return report


__all__ = [
    "ingest_path",
    "hash_html",
    "IngestReport",
    "FileIngestResult",
]
