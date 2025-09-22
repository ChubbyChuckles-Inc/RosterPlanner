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
                    team_id = self._derive_team_id(canonical_name)
                    player_rows = self._upsert_team(team_id, canonical_name, d.division)
                    teams_ingested += 1
                    players_ingested += player_rows

        summary = IngestionSummary(
            divisions_ingested=divisions_ingested,
            teams_ingested=teams_ingested,
            players_ingested=players_ingested,
            skipped_files=skipped_files,
            processed_files=processed_files,
        )
        # Record high-level ingest summary into a standardized table (provenance_summary)
        try:
            self.conn.execute(
                "CREATE TABLE IF NOT EXISTS provenance_summary(\n"
                "id INTEGER PRIMARY KEY AUTOINCREMENT,\n"
                "ingested_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,\n"
                "divisions INTEGER,\n"
                "teams INTEGER,\n"
                "players INTEGER,\n"
                "files_processed INTEGER,\n"
                "files_skipped INTEGER\n"
                ")"
            )
            self.conn.execute(
                "INSERT INTO provenance_summary(divisions, teams, players, files_processed, files_skipped) VALUES(?,?,?,?,?)",
                (
                    divisions_ingested,
                    teams_ingested,
                    players_ingested,
                    processed_files,
                    skipped_files,
                ),
            )
        except Exception:
            pass
        if self.event_bus is not None:
            try:
                self.event_bus.publish(Event("DATA_REFRESHED", payload={"summary": summary}))
            except Exception:  # pragma: no cover - non-fatal
                pass
        return summary

    # Internal helpers --------------------------------------------
    def _upsert_division(self, division_name: str):
        # For now treat provided division_id string as name; assign synthetic numeric id via hash
        # Future parsing will extract proper season + level.
        self.conn.execute(
            "INSERT OR IGNORE INTO division(division_id, name, season) VALUES(?,?,?)",
            (abs(hash(division_name)) % 10_000_000, division_name.replace("_", " "), 2025),
        )

    def _ensure_club(self, club_code: str):  # legacy helper retained (unused in new flow)
        self.conn.execute(
            "INSERT OR IGNORE INTO club(club_id, name) VALUES(?, ?)",
            (abs(hash(club_code)) % 10_000_000, club_code.replace("_", " ")),
        )

    def _upsert_team(self, team_code: str, full_team_name: str, division_name: str) -> int:
        """Upsert team with club/suffix splitting and ensure placeholder player.

        Splitting heuristic: if the last token is purely digits treat it as the
        team suffix (e.g. 'LTTV Leutzscher Füchse 1990 3' -> club='LTTV Leutzscher Füchse 1990', name='3').
        Otherwise whole name considered club and synthetic suffix '1' used (avoids empty names).
        """
        club_full_name, team_suffix = self._split_club_and_suffix(full_team_name)
        club_numeric_id = abs(hash(club_full_name.lower())) % 10_000_000
        self.conn.execute(
            "INSERT OR IGNORE INTO club(club_id, name) VALUES(?,?)",
            (club_numeric_id, club_full_name),
        )
        div_row = self.conn.execute(
            "SELECT division_id FROM division WHERE name=?",
            (division_name.replace("_", " "),),
        ).fetchone()
        if not div_row:
            return 0
        division_id = div_row[0]
        team_numeric_id = abs(hash(team_code)) % 10_000_000
        self.conn.execute(
            "INSERT OR REPLACE INTO team(team_id, club_id, division_id, name) VALUES(?,?,?,?)",
            (team_numeric_id, club_numeric_id, division_id, team_suffix),
        )
        # Parse real roster HTML if available (look for a roster file referencing this team id pattern)
        added_players = self._parse_and_upsert_players(team_numeric_id, full_team_name)
        return added_players

    # Roster Parsing ----------------------------------------------
    def _parse_and_upsert_players(self, team_numeric_id: int, full_team_name: str) -> int:
        """Attempt to locate and parse a roster HTML file for the given team.

        Strategy: search base_dir for any file under divisions whose filename contains
        the normalized team name tokens and a trailing numeric id matching the team id hash modulo pattern
        is brittle; instead we scan for roster files containing the full team name (case-insensitive).
        Parsing heuristic: extract unique text nodes within table rows or list items that look like player names
        (contain a space or an uppercase start). We ignore extremely short tokens.
        """
        try:
            import re
            from bs4 import BeautifulSoup  # type: ignore
        except Exception:
            return 0  # BeautifulSoup not installed yet

        # Build candidate files list
        roster_files: list[Path] = []
        lower_name = full_team_name.lower().replace("_", " ")
        for p in self.base_dir.rglob("team_roster_*.html"):
            try:
                txt = p.read_text(errors="ignore")
            except Exception:
                continue
            if lower_name in txt.lower():
                roster_files.append(p)
        if not roster_files:
            return 0
        inserted = 0
        seen = set(
            r[0]
            for r in self.conn.execute(
                "SELECT full_name FROM player WHERE team_id=?", (team_numeric_id,)
            ).fetchall()
        )
        for rf in roster_files:
            try:
                soup = BeautifulSoup(rf.read_text(errors="ignore"), "html.parser")
            except Exception:
                continue
            # Candidate selectors: table rows cells, list items
            candidates: list[str] = []
            for sel in ["td", "li", "span"]:
                for node in soup.select(sel):  # type: ignore
                    text = (node.get_text(" ").strip()).replace("\xa0", " ")
                    if not text:
                        continue
                    if len(text) < 4:
                        continue
                    if text.lower().startswith("geb."):
                        continue
                    # Basic name heuristic: at least one space and start with letter
                    if " " in text and re.match(r"[A-Za-zÄÖÜäöü]", text):
                        candidates.append(text)
            # Deduplicate preserving order
            unique: list[str] = []
            seen_local = set()
            for c in candidates:
                if c not in seen_local and c.lower() not in {u.lower() for u in unique}:
                    unique.append(c)
                    seen_local.add(c)
            for name in unique:
                if name in seen:
                    continue
                player_id = abs(hash((team_numeric_id, name))) % 10_000_000
                try:
                    self.conn.execute(
                        "INSERT OR IGNORE INTO player(player_id, team_id, full_name, live_pz) VALUES(?,?,?,?)",
                        (player_id, team_numeric_id, name, None),
                    )
                    seen.add(name)
                    inserted += 1
                except Exception:
                    continue
        return inserted

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
    def _derive_club_id(team_name: str) -> str:  # legacy compatibility
        return team_name.split()[0].lower()

    @staticmethod
    def _split_club_and_suffix(full_team_name: str) -> tuple[str, str]:
        tokens = full_team_name.strip().split()
        if len(tokens) >= 2 and tokens[-1].isdigit():
            return " ".join(tokens[:-1]), tokens[-1]
        return full_team_name, "1"

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
