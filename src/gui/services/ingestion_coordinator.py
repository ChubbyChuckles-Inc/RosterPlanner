"""IngestionCoordinator (Milestone 5.9.3).

Bridges scraped HTML assets into the SQLite database using repository
contracts / schema. For now this is a *minimal* ingestion pass that:

1. Runs DataAuditService to discover divisions and team roster files.
2. Derives division + team entities from filenames (no deep HTML parsing yet).
3. Performs idempotent upserts into divisions, clubs (placeholder), teams,
   and players (players are not yet parsed, placeholder only).
4. Emits an event via EventBus (if available) signaling data refresh.

Future milestones will:
- Parse actual roster HTML for player lists & attributes.
- Parse ranking table HTML for standings & match schedule.
- Compute hashes and skip unchanged ingestion (5.9.4).
- Provide transactional ingest and error channel (5.9.12, 5.9.13).
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
import sqlite3
from typing import Optional, Iterable

from .data_audit import DataAuditService
from .event_bus import EventBus, Event  # type: ignore

__all__ = ["IngestionCoordinator", "IngestionSummary"]


@dataclass
class IngestionSummary:
    divisions_ingested: int
    teams_ingested: int
    players_ingested: int
    skipped_files: int = 0
    processed_files: int = 0


class IngestionCoordinator:
    """Coordinates ingestion of scraped assets into SQLite.

    Parameters
    ----------
    base_dir: str
        Directory containing scraped HTML assets.
    conn: sqlite3.Connection
        Database connection (repositories may share this).
    event_bus: Optional[EventBus]
        Event bus for emitting post-ingest notifications.
    """

    def __init__(
        self, base_dir: str, conn: sqlite3.Connection, event_bus: Optional[EventBus] = None
    ):
        self.base_dir = Path(base_dir)
        self.conn = conn
        self.event_bus = event_bus

    # Public ------------------------------------------------------
    def run(self) -> IngestionSummary:
        self._ensure_provenance_table()
        audit = DataAuditService(str(self.base_dir)).run()
        divisions_ingested = 0
        teams_ingested = 0
        players_ingested = 0
        skipped_files = 0
        processed_files = 0

        with self.conn:  # single transaction for now (not per-division yet)
            # Upsert divisions & roster-derived teams
            for d in audit.divisions:
                self._upsert_division(d.division)
                divisions_ingested += 1
                # Ranking table provenance (not yet parsing content)
                if d.ranking_table:
                    if self._is_unchanged(d.ranking_table.path, d.ranking_table.sha1):
                        skipped_files += 1
                    else:
                        processed_files += 1
                        self._record_provenance(d.ranking_table.path, d.ranking_table.sha1)

                # --- Deduplication phase (group by numeric id extracted from filename path) ---
                # Build map: numeric_team_id -> list[(team_name, info)]
                grouped: dict[str, list[tuple[str, object]]] = {}
                for team_name, info in d.team_rosters.items():
                    numeric_id = self._extract_numeric_id_from_path(
                        info.path
                    ) or self._derive_team_id(team_name)
                    grouped.setdefault(numeric_id, []).append((team_name, info))

                for numeric_id, entries in grouped.items():
                    # Record provenance for all variants first
                    canonical_name = self._choose_canonical_name([n for n, _ in entries])
                    chosen_info = None
                    for name, info in entries:
                        if self._is_unchanged(info.path, info.sha1):
                            skipped_files += 1
                        else:
                            processed_files += 1
                            self._record_provenance(info.path, info.sha1)
                        if name == canonical_name:
                            chosen_info = info
                    # Upsert only once per numeric id using canonical name
                    team_id = self._derive_team_id(canonical_name)
                    club_id = self._derive_club_id(canonical_name)
                    self._ensure_club(club_id)
                    self._upsert_team(team_id, canonical_name, d.division, club_id)
                    teams_ingested += 1
                    # Placeholder players (none parsed yet)

        summary = IngestionSummary(
            divisions_ingested=divisions_ingested,
            teams_ingested=teams_ingested,
            players_ingested=players_ingested,
            skipped_files=skipped_files,
            processed_files=processed_files,
        )
        if self.event_bus is not None:
            try:
                self.event_bus.publish(Event("DATA_REFRESHED", payload={"summary": summary}))
            except Exception:  # pragma: no cover - non-fatal
                pass
        return summary

    # Internal helpers --------------------------------------------
    def _upsert_division(self, division_id: str):
        self.conn.execute(
            "INSERT OR IGNORE INTO divisions(id, name) VALUES(?, ?)",
            (division_id, division_id.replace("_", " ")),  # naive name until real parsing
        )

    def _ensure_club(self, club_id: str):
        self.conn.execute(
            "INSERT OR IGNORE INTO clubs(id, name) VALUES(?, ?)",
            (club_id, club_id.replace("_", " ")),  # placeholder name
        )

    def _upsert_team(self, team_id: str, name: str, division_id: str, club_id: str | None):
        self.conn.execute(
            "INSERT OR REPLACE INTO teams(id, name, division_id, club_id) VALUES(?,?,?,?)",
            (team_id, name, division_id, club_id),
        )

    # Provenance --------------------------------------------------
    def _ensure_provenance_table(self):
        self.conn.execute(
            """CREATE TABLE IF NOT EXISTS provenance(
            path TEXT PRIMARY KEY,
            sha1 TEXT NOT NULL,
            last_ingested_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            parser_version INTEGER DEFAULT 1
            )"""
        )

    def _is_unchanged(self, path: str, sha1: str) -> bool:
        cur = self.conn.execute("SELECT sha1 FROM provenance WHERE path=?", (path,))
        row = cur.fetchone()
        return bool(row and row[0] == sha1)

    def _record_provenance(self, path: str, sha1: str):
        self.conn.execute(
            "INSERT INTO provenance(path, sha1, last_ingested_at) VALUES(?,?,CURRENT_TIMESTAMP)\n"
            "ON CONFLICT(path) DO UPDATE SET sha1=excluded.sha1, last_ingested_at=CURRENT_TIMESTAMP",
            (path, sha1),
        )

    @staticmethod
    def _derive_team_id(team_name: str) -> str:
        return team_name.lower().replace(" ", "-")

    @staticmethod
    def _derive_club_id(team_name: str) -> str:
        # Heuristic: use first token as club grouping; refine later when real parsing is implemented
        return team_name.split()[0].lower()

    # New helpers -------------------------------------------------
    @staticmethod
    def _extract_numeric_id_from_path(path: str) -> str | None:
        """Attempt to extract the trailing numeric team id from a roster filename.

        Accepts patterns like:
        .../team_roster_<division>_<team_name_tokens>_<id>.html
        .../club_team_<clubname>_<team_name_tokens>_<id>.html
        Returns the numeric id string if found, else None.
        """
        import re, os

        fname = os.path.basename(path)
        m = re.search(r"_(\d+)\.html$", fname)
        return m.group(1) if m else None

    @staticmethod
    def _choose_canonical_name(variants: list[str]) -> str:
        """Select a canonical team name among variants.

        Preference order:
        1. Variant containing a separator char (dash) replaced earlier that likely indicates club prefix (longer form)
        2. Longest variant (most tokens)
        3. First in list (stable)
        """
        if not variants:
            return "unknown-team"
        # Normalize whitespace
        norm = [v.strip() for v in variants if v.strip()]
        if not norm:
            return variants[0]

        # Prefer one that has at least 2 tokens and a digit at end token (common pattern) and contains a club-like token (capitalized word with Umlaut or mixed case)
        def score(name: str) -> tuple[int, int]:
            tokens = name.split()
            has_number_suffix = 1 if (tokens and any(ch.isdigit() for ch in tokens[-1])) else 0
            length = len(tokens)
            return (has_number_suffix, length)

        norm.sort(key=score, reverse=True)
        return norm[0]
