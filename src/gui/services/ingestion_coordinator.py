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
from typing import Optional, Iterable, Tuple, List

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
        self._singular_mode = True  # auto-detected per connection
        self._table_division = "division"
        self._table_team = "team"
        self._table_club = "club"
        self._table_player = "player"
        self._table_ranking = "division_ranking"
        self._detect_schema()

    # Public ------------------------------------------------------
    def run(self) -> IngestionSummary:
        self._ensure_provenance_table()
        self._ensure_normalized_provenance_view()
        if self._singular_mode:
            self._ensure_id_map_table()
            self._ensure_ranking_table()
        else:
            # Rebind table attribute names to legacy plural schema so downstream code paths
            # that reference self._table_* write to correct tables. This keeps new logic centralized.
            self._table_division = "divisions"
            self._table_team = "teams"
            self._table_club = "clubs"
            self._table_player = "players"
        audit = DataAuditService(str(self.base_dir)).run()
        divisions_ingested = 0
        teams_ingested = 0
        players_ingested = 0
        skipped_files = 0
        processed_files = 0

        with self.conn:  # single transaction for now (not per-division yet)
            # Upsert divisions & roster-derived teams
            for d in audit.divisions:
                div_id = self._upsert_division(d.division)
                divisions_ingested += 1
                # Ranking table provenance (not yet parsing content)
                if d.ranking_table:
                    if self._is_unchanged(d.ranking_table.path, d.ranking_table.sha1):
                        skipped_files += 1
                    else:
                        processed_files += 1
                        self._record_provenance(d.ranking_table.path, d.ranking_table.sha1)
                    # Parse ranking if enabled / singular mode
                    try:
                        if self._singular_mode:
                            self._parse_and_upsert_ranking(div_id, d.ranking_table.path)
                    except Exception:
                        pass

                    # --- Deduplication phase (group by numeric id extracted from filename path) ---
                    if not self._singular_mode:
                        # Legacy plural schema: treat each roster file independently (no dedup grouping)
                        for team_name, info in d.team_rosters.items():
                            if self._is_unchanged(info.path, info.sha1):
                                skipped_files += 1
                            else:
                                processed_files += 1
                                self._record_provenance(info.path, info.sha1)
                            team_id = self._derive_team_id(team_name)
                            player_rows = self._upsert_team(team_id, team_name, d.division)
                            teams_ingested += 1
                            players_ingested += player_rows
                    else:
                        # Build map: numeric_team_id -> list[(team_name, info)] for dedup
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
    def _upsert_division(self, division_name: str) -> int | str:
        readable_name = division_name.replace("_", " ")
        if self._singular_mode:
            # Stable id mapping
            assigned = self._assign_id("division", readable_name)
            self.conn.execute(
                f"INSERT OR IGNORE INTO {self._table_division}(division_id, name, season) VALUES(?,?,?)",
                (assigned, readable_name, 2025),
            )
            return assigned
        else:
            # Plural legacy schema uses textual id (reuse name hash string for compatibility)
            div_id = str(abs(hash(readable_name)) % 10_000_000)
            try:
                self.conn.execute(
                    "INSERT OR IGNORE INTO divisions(id, name) VALUES(?,?)",
                    (div_id, readable_name),
                )
            except Exception:
                pass
            return div_id

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
        readable_division = division_name.replace("_", " ")
        if self._singular_mode:
            club_id = self._assign_id("club", club_full_name)
            self.conn.execute(
                f"INSERT OR IGNORE INTO {self._table_club}(club_id, name) VALUES(?,?)",
                (club_id, club_full_name),
            )
            div_row = self.conn.execute(
                f"SELECT division_id FROM {self._table_division} WHERE name=?",
                (readable_division,),
            ).fetchone()
            if not div_row:
                return 0
            division_id = div_row[0]
            team_id_assigned = self._assign_id("team", full_team_name)
            self.conn.execute(
                f"INSERT OR REPLACE INTO {self._table_team}(team_id, club_id, division_id, name) VALUES(?,?,?,?)",
                (team_id_assigned, club_id, division_id, team_suffix),
            )
            added_players = self._parse_and_upsert_players(team_id_assigned, full_team_name)
            if added_players == 0:  # ensure at least placeholder only if none parsed
                placeholder_id = self._assign_id("player", f"{team_id_assigned}:Placeholder Player")
                try:
                    self.conn.execute(
                        f"INSERT OR IGNORE INTO {self._table_player}(player_id, team_id, full_name, live_pz) VALUES(?,?,?,?)",
                        (placeholder_id, team_id_assigned, "Placeholder Player", None),
                    )
                    added_players = 1
                except Exception:
                    pass
            return added_players
        else:  # plural legacy fallback
            # Use textual IDs based on lower tokens (backwards compatibility with tests)
            club_id = club_full_name.split()[0].lower()
            try:
                self.conn.execute(
                    "INSERT OR IGNORE INTO clubs(id, name) VALUES(?,?)",
                    (club_id, club_full_name),
                )
            except Exception:
                pass
            div_row = self.conn.execute(
                "SELECT id FROM divisions WHERE name=?",
                (readable_division,),
            ).fetchone()
            if not div_row:
                return 0
            division_id = div_row[0]
            # Legacy original collapsed different roster variants; enhance by appending numeric suffix when present
            suffix = team_suffix if team_suffix.isdigit() else "1"
            base_prefix = team_code.split("-")[0]
            team_id = f"{base_prefix}{suffix}" if base_prefix and suffix else base_prefix
            try:
                self.conn.execute(
                    "INSERT OR IGNORE INTO teams(id, name, division_id, club_id) VALUES(?,?,?,?)",
                    (team_id, team_suffix, division_id, club_id),
                )
            except Exception:
                pass
            # Legacy flow does not ingest players (skip)
            return 0

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

        # Build candidate file list containing the full team name text
        roster_files: list[Path] = []
        lower_name = full_team_name.lower().replace("_", " ")
        for p in self.base_dir.rglob("team_roster_*.html"):
            try:
                txt = self._read_html(p)
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
                soup = BeautifulSoup(self._read_html(rf), "html.parser")
            except Exception:
                continue
            gathered: list[tuple[str, int | None]] = []
            # Locate roster table with both 'Spieler' and 'LivePZ'
            target_table = None
            for tbl in soup.find_all("table"):
                text_sample = " ".join(c.get_text(" ").lower() for c in tbl.find_all("td")[:30])
                if "spieler" in text_sample and "livepz" in text_sample:
                    target_table = tbl
                    break
            if target_table:
                for tr in target_table.find_all("tr"):
                    cells = [c.get_text(" ").strip() for c in tr.find_all("td")]
                    if len(cells) < 6:
                        continue
                    pos_token = cells[1]
                    if not (
                        pos_token.rstrip(".").isdigit()
                        or "Er/" in pos_token
                        or pos_token.endswith(".")
                    ):
                        continue
                    name_candidate = cells[3].strip() if len(cells) > 3 else ""
                    if not name_candidate or len(name_candidate) < 3:
                        continue
                    # Extract last pure integer as LivePZ (ignore scores containing ':')
                    live_pz = None
                    for token in reversed(cells):
                        t = token.replace("\xa0", "").strip()
                        if t.isdigit():
                            if ":" in t:
                                continue
                            try:
                                live_pz = int(t)
                            except Exception:
                                live_pz = None
                            break
                    gathered.append((name_candidate, live_pz))
            # Fallback generic if specialized failed
            if len(gathered) < 2:
                generic_candidates: list[str] = []
                for tbl in soup.find_all("table")[:3]:
                    header = []
                    for row in tbl.find_all("tr"):
                        cells = [c.get_text(" ").strip() for c in row.find_all(["td", "th"])]
                        if not cells:
                            continue
                        if not header and any(h.lower() in {"spieler", "name"} for h in cells):
                            header = [h.lower() for h in cells]
                            continue
                        name_idx = None
                        for i, h in enumerate(header):
                            if h in {"spieler", "name"}:
                                name_idx = i
                                break
                        if name_idx is not None and name_idx < len(cells):
                            cand = cells[name_idx].strip()
                            if " " in cand and 3 <= len(cand) <= 80:
                                generic_candidates.append(cand)
                noise = {"aktuelle tabelle", "allgemeine ligastatistiken"}
                for c in generic_candidates:
                    if c.lower() in noise:
                        continue
                    gathered.append((c, None))
            # Insert unique
            seen_local = set()
            for name, lpz in gathered:
                norm = name.strip()
                if not norm or norm.lower() in seen_local or norm in seen:
                    continue
                seen_local.add(norm.lower())
                player_id = abs(hash((team_numeric_id, norm))) % 10_000_000
                try:
                    self.conn.execute(
                        f"INSERT OR IGNORE INTO {self._table_player}(player_id, team_id, full_name, live_pz) VALUES(?,?,?,?)",
                        (player_id, team_numeric_id, norm, lpz),
                    )
                    inserted += 1
                    seen.add(norm)
                except Exception:
                    pass
        return inserted

    # Ranking Parsing ---------------------------------------------
    def _ensure_ranking_table(self):
        try:
            self.conn.execute(
                f"CREATE TABLE IF NOT EXISTS {self._table_ranking}(division_id INTEGER, position INTEGER, team_name TEXT, matches_played INTEGER, wins INTEGER, draws INTEGER, losses INTEGER, points INTEGER, PRIMARY KEY(division_id, position))"
            )
        except Exception:
            pass

    def _parse_and_upsert_ranking(self, division_id: int | str, path: str):
        try:
            from bs4 import BeautifulSoup  # type: ignore
        except Exception:
            return
        try:
            html = Path(path).read_text(errors="ignore")
        except Exception:
            return
        try:
            soup = BeautifulSoup(html, "html.parser")
        except Exception:
            return
        table = None
        # Prefer table with ranking/tabelle keyword
        for t in soup.find_all("table"):
            cls = " ".join(t.get("class", [])).lower() if t.get("class") else ""
            if any(k in cls for k in ["ranking", "tabelle", "standings", "tabelle"]):
                table = t
                break
        if table is None:
            tables = soup.find_all("table")
            table = tables[0] if tables else None
        if table is None:
            return
        rows = []
        for tr in table.find_all("tr"):
            cells = [c.get_text(" ").strip() for c in tr.find_all(["td", "th"])]
            if len(cells) < 2:
                continue
            rows.append(cells)
        # Heuristic: first row headers if contains non-numeric token 'Team'
        if rows and any("team" in c.lower() or "mann" in c.lower() for c in rows[0]):
            rows = rows[1:]
        position = 0
        for r in rows:
            # Determine position and team name
            pos_candidate = r[0]
            if not pos_candidate.isdigit():
                continue
            position = int(pos_candidate)
            team_name = r[1]
            # Points heuristic: last numeric cell
            points = None
            for token in reversed(r):
                if token.isdigit():
                    points = int(token)
                    break
            try:
                self.conn.execute(
                    f"INSERT OR REPLACE INTO {self._table_ranking}(division_id, position, team_name, points, matches_played, wins, draws, losses) VALUES(?,?,?,?,NULL,NULL,NULL,NULL)",
                    (division_id, position, team_name, points),
                )
            except Exception:
                pass

    # Stable ID Mapping -------------------------------------------
    def _ensure_id_map_table(self):
        try:
            self.conn.execute(
                "CREATE TABLE IF NOT EXISTS id_map(\n"
                "entity_type TEXT NOT NULL,\n"
                "source_key TEXT NOT NULL,\n"
                "assigned_id INTEGER PRIMARY KEY AUTOINCREMENT,\n"
                "UNIQUE(entity_type, source_key)\n"
                ")"
            )
        except Exception:
            pass

    def _assign_id(self, entity_type: str, source_key: str) -> int:
        cur = self.conn.execute(
            "SELECT assigned_id FROM id_map WHERE entity_type=? AND source_key=?",
            (entity_type, source_key),
        )
        row = cur.fetchone()
        if row:
            return int(row[0])
        self.conn.execute(
            "INSERT INTO id_map(entity_type, source_key) VALUES(?,?)",
            (entity_type, source_key),
        )
        return int(
            self.conn.execute(
                "SELECT assigned_id FROM id_map WHERE entity_type=? AND source_key=?",
                (entity_type, source_key),
            ).fetchone()[0]
        )

    # Schema detection ---------------------------------------------
    def _detect_schema(self):
        try:
            cur = self.conn.execute("SELECT name FROM sqlite_master WHERE type='table'")
            tables = {r[0] for r in cur.fetchall()}
            if "division" not in tables and "divisions" in tables:
                self._singular_mode = False
        except Exception:
            self._singular_mode = True

    # Provenance normalization view -------------------------------
    def _ensure_normalized_provenance_view(self):
        try:
            self.conn.execute(
                "CREATE VIEW IF NOT EXISTS provenance_normalized AS \n"
                "SELECT 'file' AS kind, path, sha1, last_ingested_at AS ingested_at, NULL AS divisions, NULL AS teams, NULL AS players, NULL AS files_processed, NULL AS files_skipped FROM provenance\n"
                "UNION ALL\n"
                "SELECT 'summary' AS kind, NULL, NULL, ingested_at, divisions, teams, players, files_processed, files_skipped FROM provenance_summary"
            )
        except Exception:
            pass

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
        """Heuristically split a raw team label into (club_name, team_suffix).

        Rules:
        - Trailing small integer (1..20) -> team suffix (e.g. 'LTTV Leutzscher Füchse 1990 3').
        - Trailing year (1850-2099) alone => part of club, assign suffix '1'.
        - Pattern '<club> <year> <n>' -> year stays in club, n becomes suffix.
        - Otherwise whole string is club, suffix '1'.
        """
        tokens = full_team_name.strip().split()
        if not tokens:
            return full_team_name, "1"

        def is_year(tok: str) -> bool:
            return tok.isdigit() and 1850 <= int(tok) <= 2099

        def is_team_num(tok: str) -> bool:
            return tok.isdigit() and 1 <= int(tok) <= 20

        if len(tokens) >= 2:
            last = tokens[-1]
            prev = tokens[-2]
            if is_team_num(last):
                # If previous token is a year include it in club name
                return " ".join(tokens[:-1]), last
            if is_year(last):
                return full_team_name, "1"
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

    @staticmethod
    def _read_html(path: Path) -> str:
        """Robust file reader attempting utf-8 then latin-1.

        Some league pages occasionally contain mojibake; this makes parsing
        resilient and reduces decoding noise in player names.
        """
        try:
            return path.read_text(encoding="utf-8")
        except Exception:
            try:
                return path.read_bytes().decode("latin-1")
            except Exception:
                return path.read_text(errors="ignore")
