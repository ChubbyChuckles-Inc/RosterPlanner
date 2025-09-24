"""Ingestion Coordinator (clean reconstruction for Milestone 5.9.24).

Includes: SAVEPOINT per division, provenance tracking & summary, stable id mapping,
heuristic roster + ranking parsing, optional consistency validation hook, event bus
notifications, and structured JSONL lifecycle logging (ingest_events.jsonl).
"""

from __future__ import annotations

from dataclasses import dataclass, field, asdict
from pathlib import Path
import sqlite3
import json
import time
from typing import Optional
import re

from .data_audit import DataAuditService
from .event_bus import EventBus, Event  # type: ignore
from .service_locator import services  # lazy access for metrics service

__all__ = ["IngestionCoordinator", "IngestionSummary", "IngestError"]

# Backward compatibility alias (some dynamic imports may look for 'ingestion_coordinator')
ingestion_coordinator = None  # sentinel to satisfy getattr checks


@dataclass
class IngestError:
    division: str
    message: str
    severity: str = "error"
    file: str | None = None


@dataclass
class IngestionSummary:
    divisions_ingested: int
    teams_ingested: int
    players_ingested: int
    skipped_files: int = 0
    processed_files: int = 0
    errors: list[IngestError] = field(default_factory=list)


class IngestionCoordinator:
    def __init__(
        self, base_dir: str, conn: sqlite3.Connection, event_bus: Optional[EventBus] = None
    ):
        self.base_dir = Path(base_dir)
        self.conn = conn
        self.event_bus = event_bus
        self._singular_mode = True
        self._table_division = "division"
        self._table_team = "team"
        self._table_club = "club"
        self._table_player = "player"
        self._table_ranking = "division_ranking"
        self._detect_schema()

    def run(self, *, force: bool = False) -> IngestionSummary:
        start_ts = time.time()
        self._ensure_provenance_table()
        self._ensure_normalized_provenance_view()
        if self._singular_mode:
            self._ensure_id_map_table()
            self._ensure_ranking_table()
        else:
            self._table_division = "divisions"
            self._table_team = "teams"
            self._table_club = "clubs"
            self._table_player = "players"
        audit = DataAuditService(str(self.base_dir)).run()
        logger = _IngestEventLogger.try_create(self.base_dir)
        if logger:
            logger.emit(
                "ingest.start",
                {
                    "base_dir": str(self.base_dir),
                    "divisions_discovered": len(audit.divisions),
                    "total_rosters": audit.total_team_rosters,
                    "total_rankings": audit.total_ranking_tables,
                },
            )
        divisions_ingested = teams_ingested = players_ingested = 0
        skipped_files = processed_files = 0
        errors: list[IngestError] = []
        for idx, d in enumerate(audit.divisions, start=1):
            sp = f"div_ingest_{idx}"
            try:
                self.conn.execute(f"SAVEPOINT {sp}")
                if logger:
                    logger.emit("division.start", {"division": d.division, "index": idx})
                # Some test subclasses override _ingest_single_division without a force kwarg.
                try:
                    result = self._ingest_single_division(d, force=force)  # type: ignore[arg-type]
                except TypeError:
                    # Retry without keyword for backward compatibility in tests
                    result = self._ingest_single_division(d)  # type: ignore[call-arg]
                if result is None:
                    self.conn.execute(f"RELEASE SAVEPOINT {sp}")
                    if logger:
                        logger.emit("division.skipped", {"division": d.division})
                    continue
                div_add, team_add, player_add, skip_delta, proc_delta = result
                divisions_ingested += div_add
                teams_ingested += team_add
                players_ingested += player_add
                skipped_files += skip_delta
                processed_files += proc_delta
                self.conn.execute(f"RELEASE SAVEPOINT {sp}")
                if logger:
                    logger.emit(
                        "division.success",
                        {
                            "division": d.division,
                            "teams": team_add,
                            "players": player_add,
                            "processed": proc_delta,
                            "skipped": skip_delta,
                        },
                    )
            except Exception as e:  # noqa: BLE001
                try:
                    self.conn.execute(f"ROLLBACK TO {sp}")
                    self.conn.execute(f"RELEASE SAVEPOINT {sp}")
                except Exception:
                    pass
                err = IngestError(division=d.division, message=str(e))
                errors.append(err)
                self._persist_error(err)
                if logger:
                    logger.emit("division.error", {"division": d.division, "message": str(e)})
                continue
        summary = IngestionSummary(
            divisions_ingested=divisions_ingested,
            teams_ingested=teams_ingested,
            players_ingested=players_ingested,
            skipped_files=skipped_files,
            processed_files=processed_files,
            errors=errors,
        )
        if logger:
            logger.emit("ingest.complete", {**asdict(summary), "error_count": len(errors)})
        try:  # pragma: no cover
            from .consistency_validation_service import ConsistencyValidationService

            ConsistencyValidationService.run_and_register(self.conn)
        except Exception:
            pass
        try:  # provenance summary
            self.conn.execute(
                "CREATE TABLE IF NOT EXISTS provenance_summary("
                "id INTEGER PRIMARY KEY AUTOINCREMENT,"
                "ingested_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,"
                "divisions INTEGER, teams INTEGER, players INTEGER, files_processed INTEGER, files_skipped INTEGER)"
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
        # Record run metrics (best effort; never raises)
        try:
            from .ingest_metrics_service import IngestMetricsService

            metrics = services.try_get("ingest_metrics")
            if metrics is None:
                metrics = IngestMetricsService()
                services.register("ingest_metrics", metrics, allow_override=True)
            duration_ms = (time.time() - start_ts) * 1000.0
            metrics.append_from_summary(summary, duration_ms)
        except Exception:
            pass
        if self.event_bus is not None:
            try:  # pragma: no cover
                self.event_bus.publish("DATA_REFRESHED", {"summary": summary})
                for e in errors:
                    self.event_bus.publish(
                        "INGEST_ERROR",
                        {
                            "division": e.division,
                            "message": e.message,
                            "severity": e.severity,
                            "file": e.file,
                        },
                    )
            except Exception:
                pass
        return summary

    # ---- Ingestion inner phases -------------------------------------------------
    def _ingest_single_division(
        self, d, *, force: bool = False
    ) -> tuple[int, int, int, int, int] | None:
        divisions_ingested = teams_ingested = players_ingested = 0
        skipped_files = processed_files = 0
        div_id = self._upsert_division(d.division)
        divisions_ingested += 1
        # Ranking table (optional)
        if d.ranking_table:
            if not force and self._is_unchanged(d.ranking_table.path, d.ranking_table.sha1):
                skipped_files += 1
            else:
                processed_files += 1
                self._record_provenance(d.ranking_table.path, d.ranking_table.sha1)
            if self._singular_mode:
                try:
                    self._parse_and_upsert_ranking(div_id, d.ranking_table.path)
                except Exception:
                    pass
        # Team rosters (always attempt even if ranking table missing)
        if not self._singular_mode:
            base_counts: dict[str, int] = {}
            group_map: dict[str, list[str]] = {}
            for team_name, info in d.team_rosters.items():
                numeric_id = self._extract_numeric_id_from_path(info.path) or self._derive_team_id(
                    team_name
                )
                group_map.setdefault(numeric_id, []).append(team_name)
            for numeric_id, variants in group_map.items():  # noqa: B007
                canonical_name = self._choose_canonical_name(variants)
                for team_name in variants:
                    info = d.team_rosters[team_name]
                    if (not force) and self._is_unchanged(info.path, info.sha1):
                        skipped_files += 1
                    else:
                        processed_files += 1
                        self._record_provenance(info.path, info.sha1)
                force_full = any(c.isalpha() for c in canonical_name)
                player_rows = self._upsert_team(
                    self._derive_team_id(canonical_name),
                    canonical_name,
                    d.division,
                    base_counts,
                    force_full_name=force_full,
                )
                teams_ingested += 1
                players_ingested += player_rows
        else:
            # Singular schema: enumerate teams from BOTH roster filename heuristics AND (if available)
            # the ranking table navigation (authoritative). This addresses cases where some roster
            # files are missing or filename heuristics fail, leading to incomplete division teams.
            ranking_teams: list[dict] = []
            ranking_roster_map: dict[str, Path] = {}  # team_name(lower) -> roster path (if matched)
            try:
                if d.ranking_table and Path(d.ranking_table.path).exists():
                    # Late import to avoid circulars
                    from parsing.ranking_parser import parse_ranking_table  # type: ignore

                    html = Path(d.ranking_table.path).read_text(encoding="utf-8", errors="ignore")
                    _div_name_from_html, nav_entries = parse_ranking_table(
                        html, source_hint=Path(d.ranking_table.path).name
                    )
                    ranking_teams = nav_entries
            except Exception:
                ranking_teams = []

            # Build index of roster files by trailing numeric id (L3P) and by normalized name
            id_index: dict[str, Path] = {}
            name_index: dict[str, Path] = {}

            def _norm_name(s: str) -> str:
                import unicodedata, re as _re

                s2 = unicodedata.normalize("NFKD", s)
                s2 = "".join(c for c in s2 if not unicodedata.combining(c))
                s2 = s2.lower()
                # Replace common separators with space, drop punctuation, collapse whitespace
                s2 = s2.replace("-", " ").replace("_", " ")
                s2 = _re.sub(r"[^a-z0-9 ]+", " ", s2)
                s2 = _re.sub(r"\s+", " ", s2).strip()
                return s2

            for team_name, info in d.team_rosters.items():
                p = Path(info.path)
                numeric_id = self._extract_numeric_id_from_path(p.name)
                if numeric_id:
                    id_index.setdefault(numeric_id, p)
                name_index.setdefault(_norm_name(team_name), p)

            # Map of normalized team key -> metadata about ingested team
            # Used to collapse hyphen/space/diacritic variants and enrich already-created
            # teams with roster player data when the variant roster file is discovered later.
            processed_team_map: dict[str, dict] = {}

            def ingest_team(team_name: str, roster_path: Path | None):
                nonlocal teams_ingested, players_ingested, skipped_files, processed_files
                norm_key = _norm_name(team_name)

                # If we have a roster file, attempt to extract refined Club | Team designation
                # mirroring the logic in db.ingest._extract_club_and_team_from_title so that
                # GUI-triggered ingestion produces identical canonical team names.
                if roster_path and roster_path.exists():
                    try:
                        html_txt = roster_path.read_text(encoding="utf-8", errors="ignore")
                    except Exception:
                        html_txt = ""
                    if html_txt:
                        m = re.search(r" - Team ([^,<]+?),\s*([^<]+)</title>", html_txt, re.IGNORECASE)
                        club_team: tuple[str, str] | None = None
                        if m:
                            club = m.group(1).strip()
                            team_designation = m.group(2).strip()
                            if club and team_designation:
                                club_team = (club, team_designation)
                        else:
                            # Fallback heuristic (find last occurrence of ' - Team ')
                            lower = html_txt.lower()
                            idx_t = lower.rfind(" - team ")
                            if idx_t != -1:
                                after = html_txt[idx_t + len(" - team ") :]
                                end_idx = after.lower().find("</title>")
                                if end_idx != -1:
                                    after = after[:end_idx]
                                parts = after.split(",", 1)
                                if len(parts) == 2:
                                    c_candidate = parts[0].strip()
                                    t_candidate = parts[1].strip()
                                    if c_candidate and t_candidate:
                                        club_team = (c_candidate, t_candidate)
                        if club_team:
                            club_name, team_designation = club_team
                            combined_name = f"{club_name} | {team_designation}"
                            if combined_name != team_name:
                                # Attempt in-place rename of existing team row (avoid duplicates)
                                try:
                                    readable_division = d.division.replace("_", " ")
                                    div_row = self.conn.execute(
                                        f"SELECT division_id FROM {self._table_division} WHERE name=?",
                                        (readable_division,),
                                    ).fetchone()
                                    if div_row:
                                        division_id_val = div_row[0]
                                        cur = self.conn.execute(
                                            f"SELECT team_id FROM {self._table_team} WHERE division_id=? AND name=?",
                                            (division_id_val, team_name),
                                        ).fetchone()
                                        if cur:
                                            # Only rename if combined not already present
                                            dup = self.conn.execute(
                                                f"SELECT 1 FROM {self._table_team} WHERE division_id=? AND name=?",
                                                (division_id_val, combined_name),
                                            ).fetchone()
                                            if not dup:
                                                self.conn.execute(
                                                    f"UPDATE {self._table_team} SET name=? WHERE team_id=?",
                                                    (combined_name, cur[0]),
                                                )
                                                team_name = combined_name
                                            else:
                                                team_name = combined_name
                                        else:
                                            team_name = combined_name
                                    else:
                                        team_name = combined_name
                                except Exception:
                                    # Fall back silently (rename failure should not abort ingestion)
                                    pass
                                norm_key = _norm_name(team_name)

                # If we've already ingested a variant of this team and now have a roster file,
                # parse players into the existing team instead of creating a duplicate.
                if norm_key in processed_team_map:
                    if roster_path and roster_path.exists():
                        meta = processed_team_map[norm_key]
                        if not meta[
                            "players_added"
                        ]:  # only enrich if we don't have real players yet
                            # provenance recording for this roster file (may be a new variant filename)
                            info = d.team_rosters.get(team_name)
                            if info:
                                if (not force) and self._is_unchanged(info.path, info.sha1):
                                    skipped_files += 1
                                else:
                                    processed_files += 1
                                    self._record_provenance(info.path, info.sha1)
                            else:
                                try:
                                    content = roster_path.read_bytes()
                                except Exception:
                                    content = b""
                                import hashlib as _hashlib

                                sha1 = _hashlib.sha1(content).hexdigest()
                                if (not force) and self._is_unchanged(str(roster_path), sha1):
                                    skipped_files += 1
                                else:
                                    processed_files += 1
                                    self._record_provenance(str(roster_path), sha1)
                            try:
                                added = self._parse_and_upsert_players(
                                    meta["team_id"], meta["full_name"], roster_paths=[roster_path]
                                )
                            except Exception:
                                added = 0
                            if added > 0:
                                players_ingested += added
                                # Remove placeholder player if present
                                try:
                                    self.conn.execute(
                                        "DELETE FROM player WHERE team_id=? AND full_name='Placeholder Player'",
                                        (meta["team_id"],),
                                    )
                                except Exception:
                                    pass
                                meta["players_added"] = True
                    return

                roster_paths: list[Path] | None = None
                if roster_path and roster_path.exists():
                    # Provenance handling per roster file
                    info = d.team_rosters.get(team_name)
                    # If we have an AuditFileInfo entry use its hash; otherwise hash lazily
                    if info:
                        if (not force) and self._is_unchanged(info.path, info.sha1):
                            skipped_files += 1
                        else:
                            processed_files += 1
                            self._record_provenance(info.path, info.sha1)
                    else:
                        try:
                            content = roster_path.read_bytes()
                        except Exception:
                            content = b""
                        import hashlib

                        sha1 = hashlib.sha1(content).hexdigest()
                        if (not force) and self._is_unchanged(str(roster_path), sha1):
                            skipped_files += 1
                        else:
                            processed_files += 1
                            self._record_provenance(str(roster_path), sha1)
                    roster_paths = [roster_path]
                # Upsert (players parsed only if roster_paths provided) with resilience
                players_added = 0
                try:
                    players_added = self._upsert_team(
                        self._derive_team_id(team_name),
                        team_name,
                        d.division,
                        roster_paths=roster_paths,
                    )
                    teams_ingested += 1
                    players_ingested += players_added
                except Exception as te:  # noqa: BLE001
                    # Record error but continue with other teams
                    try:
                        self._persist_error(
                            IngestError(
                                division=d.division,
                                message=f"team_ingest_failed:{team_name}:{te}",
                                severity="warn",
                            )
                        )
                    except Exception:
                        pass
                # Record normalized key metadata so later variants can enrich instead of duplicate
                try:
                    existing_team_id = self._assign_id("team", team_name)
                except Exception:
                    existing_team_id = -1
                processed_team_map[norm_key] = {
                    "team_id": existing_team_id,
                    "full_name": team_name,
                    "players_added": players_added > 0,
                }

            # 1. Ingest teams from ranking navigation first (authoritative ordering)
            for entry in ranking_teams:
                tname = entry.get("team_name")
                if not tname:
                    continue
                roster_path: Path | None = None
                # Match by team id (L3P) if provided
                tid = entry.get("team_id")
                if tid and tid in id_index:
                    roster_path = id_index[tid]
                else:
                    # Name-based fallback with normalization (case/diacritics/punct-insensitive)
                    roster_path = name_index.get(_norm_name(tname))
                # Even if no roster_path matched, ingest the team (will add placeholder player)
                ingest_team(tname, roster_path)

            # 2. Ingest any remaining roster-derived teams not present in ranking nav (edge cases).
            # Duplicates are avoided via processed_team_names. This ensures that if the ranking
            # table parser missed a valid team (HTML variant) we still surface it from the roster set.
            for team_name, info in d.team_rosters.items():
                if _norm_name(team_name) in processed_team_map:
                    # Either already ingested or will be enriched inside ingest_team
                    ingest_team(team_name, Path(info.path))
                    continue
                ingest_team(team_name, Path(info.path))
        return (
            divisions_ingested,
            teams_ingested,
            players_ingested,
            skipped_files,
            processed_files,
        )

    # ---- Error persistence -------------------------------------------------------
    def _persist_error(self, err: IngestError):  # pragma: no cover
        try:
            self.conn.execute(
                "CREATE TABLE IF NOT EXISTS ingest_error(id INTEGER PRIMARY KEY AUTOINCREMENT, occurred_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP, division TEXT, file TEXT, severity TEXT, message TEXT)"
            )
            self.conn.execute(
                "INSERT INTO ingest_error(division, file, severity, message) VALUES(?,?,?,?)",
                (err.division, err.file, err.severity, err.message),
            )
        except Exception:
            pass

    # ---- Helpers / schema -------------------------------------------------------
    def _upsert_division(self, division_name: str) -> int | str:
        readable_name = division_name.replace("_", " ")
        if self._singular_mode:
            assigned = self._assign_id("division", readable_name)
            self.conn.execute(
                f"INSERT OR IGNORE INTO {self._table_division}(division_id, name, season) VALUES(?,?,?)",
                (assigned, readable_name, 2025),
            )
            return assigned
        div_id = str(abs(hash(readable_name)) % 10_000_000)
        try:
            self.conn.execute(
                "INSERT OR IGNORE INTO divisions(id, name) VALUES(?,?)", (div_id, readable_name)
            )
        except Exception:
            pass
        return div_id

    def _ensure_club(self, club_code: str):  # legacy
        self.conn.execute(
            "INSERT OR IGNORE INTO club(club_id, name) VALUES(?, ?)",
            (abs(hash(club_code)) % 10_000_000, club_code.replace("_", " ")),
        )

    def _upsert_team(
        self,
        team_code: str,
        full_team_name: str,
        division_name: str,
        base_counts: dict[str, int] | None = None,
        *,
        force_full_name: bool = False,
        roster_paths: list[Path] | None = None,
    ) -> int:
        club_full_name, team_suffix = self._split_club_and_suffix(full_team_name)
        readable_division = division_name.replace("_", " ")
        if self._singular_mode:
            club_id = self._assign_id("club", club_full_name)
            self.conn.execute(
                f"INSERT OR IGNORE INTO {self._table_club}(club_id, name) VALUES(?,?)",
                (club_id, club_full_name),
            )
            div_row = self.conn.execute(
                f"SELECT division_id FROM {self._table_division} WHERE name=?", (readable_division,)
            ).fetchone()
            if not div_row:
                return 0
            division_id = div_row[0]
            # Derive stored team name: if suffix is numeric and club_full_name already
            # contains a year token (heuristic: 4-digit number), we use just the numeric
            # suffix ("1", "2", ...) as the team name so queries expecting numbered
            # teams succeed. Otherwise fall back to full name to avoid collisions.
            team_id_assigned = self._assign_id("team", full_team_name)
            stored_team_name = full_team_name
            try:
                import re as _re

                has_year = bool(_re.search(r"\b(18|19|20)\d{2}\b", club_full_name))
                if has_year and team_suffix.isdigit():
                    stored_team_name = team_suffix  # numbered variant
            except Exception:
                pass
            # Attempt to add canonical_name column if not present (lazy migration assist)
            try:
                self.conn.execute(f"ALTER TABLE {self._table_team} ADD COLUMN canonical_name TEXT")
            except Exception:
                pass

            # Compute canonical normalization (mirror of _norm_name logic used earlier)
            def _canon(s: str) -> str:
                import unicodedata, re as _re

                s2 = unicodedata.normalize("NFKD", s)
                s2 = "".join(c for c in s2 if not unicodedata.combining(c)).lower()
                s2 = s2.replace("-", " ").replace("_", " ")
                s2 = _re.sub(r"[^a-z0-9 ]+", " ", s2)
                s2 = _re.sub(r"\s+", " ", s2).strip()
                return s2

            canonical_name = _canon(stored_team_name)
            try:
                self.conn.execute(
                    f"INSERT OR REPLACE INTO {self._table_team}(team_id, club_id, division_id, name, canonical_name) VALUES(?,?,?,?,?)",
                    (team_id_assigned, club_id, division_id, stored_team_name, canonical_name),
                )
            except Exception:
                # Fallback if column not present (legacy) – earlier insert pattern
                self.conn.execute(
                    f"INSERT OR REPLACE INTO {self._table_team}(team_id, club_id, division_id, name) VALUES(?,?,?,?)",
                    (team_id_assigned, club_id, division_id, stored_team_name),
                )
            added_players = self._parse_and_upsert_players(
                team_id_assigned, full_team_name, roster_paths=roster_paths
            )
            if added_players == 0:
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
        club_id = club_full_name.split()[0].lower()
        try:
            self.conn.execute(
                "INSERT OR IGNORE INTO clubs(id, name) VALUES(?,?)", (club_id, club_full_name)
            )
        except Exception:
            pass
        div_row = self.conn.execute(
            "SELECT id FROM divisions WHERE name=?", (readable_division,)
        ).fetchone()
        if not div_row:
            return 0
        suffix = team_suffix if team_suffix.isdigit() else "1"
        slug_tokens = [t for t in team_code.split("-") if t]
        base_prefix = slug_tokens[0] if slug_tokens else team_code
        if base_counts is not None:
            count = base_counts.get(base_prefix, 0) + 1
            base_counts[base_prefix] = count
            team_id = f"{base_prefix}{count}"
        else:
            team_id = base_prefix if suffix == "1" else f"{base_prefix}{suffix}"
        try:
            stored_name = full_team_name if force_full_name else team_suffix
            # Attempt to add canonical_name column for legacy plural path (if user manually added)
            canonical_name = stored_name.lower().replace("-", " ")
            try:
                self.conn.execute("ALTER TABLE teams ADD COLUMN canonical_name TEXT")
            except Exception:
                pass
            try:
                self.conn.execute(
                    "INSERT OR IGNORE INTO teams(id, name, division_id, club_id, canonical_name) VALUES(?,?,?,?,?)",
                    (team_id, stored_name, div_row[0], club_id, canonical_name),
                )
            except Exception:
                self.conn.execute(
                    "INSERT OR IGNORE INTO teams(id, name, division_id, club_id) VALUES(?,?,?,?)",
                    (team_id, stored_name, div_row[0], club_id),
                )
        except Exception:
            pass
        return 0

    def _parse_and_upsert_players(
        self,
        team_numeric_id: int,
        full_team_name: str,
        *,
        roster_paths: list[Path] | None = None,
    ) -> int:
        try:
            from bs4 import BeautifulSoup  # type: ignore
        except Exception:
            return 0
        # Limit roster file search strictly to provided paths (exact team association)
        # falling back to heuristic content search only if explicit paths omitted.
        roster_files: list[Path] = []
        if roster_paths:
            roster_files = [p for p in roster_paths if p.exists()]
        if not roster_files:
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
        # After successfully inserting real players, purge placeholder if present
        if inserted > 0:
            try:
                self.conn.execute(
                    "DELETE FROM player WHERE team_id=? AND full_name='Placeholder Player'",
                    (team_numeric_id,),
                )
            except Exception:
                pass
        return inserted

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
        if rows and any("team" in c.lower() or "mann" in c.lower() for c in rows[0]):
            rows = rows[1:]
        for r in rows:
            pos_candidate = r[0]
            if not pos_candidate.isdigit():
                continue
            position = int(pos_candidate)
            team_name = r[1]
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

    def _ensure_id_map_table(self):
        try:
            self.conn.execute(
                "CREATE TABLE IF NOT EXISTS id_map(entity_type TEXT NOT NULL, source_key TEXT NOT NULL, assigned_id INTEGER PRIMARY KEY AUTOINCREMENT, UNIQUE(entity_type, source_key))"
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
            "INSERT INTO id_map(entity_type, source_key) VALUES(?,?)", (entity_type, source_key)
        )
        return int(
            self.conn.execute(
                "SELECT assigned_id FROM id_map WHERE entity_type=? AND source_key=?",
                (entity_type, source_key),
            ).fetchone()[0]
        )

    # Schema detection (restored)
    def _detect_schema(self):
        try:
            tables = {
                r[0]
                for r in self.conn.execute(
                    "SELECT name FROM sqlite_master WHERE type='table'"
                ).fetchall()
            }
            if "division" not in tables and "divisions" in tables:
                self._singular_mode = False
        except Exception:
            self._singular_mode = True

    def _ensure_normalized_provenance_view(self):
        try:
            self.conn.execute(
                "CREATE VIEW IF NOT EXISTS provenance_normalized AS "
                "SELECT 'file' AS kind, path, sha1, last_ingested_at AS ingested_at, NULL AS divisions, NULL AS teams, NULL AS players, NULL AS files_processed, NULL AS files_skipped FROM provenance "
                "UNION ALL "
                "SELECT 'summary' AS kind, NULL, NULL, ingested_at, divisions, teams, players, files_processed, files_skipped FROM provenance_summary"
            )
        except Exception:
            pass

    def _ensure_provenance_table(self):
        self.conn.execute(
            "CREATE TABLE IF NOT EXISTS provenance(path TEXT PRIMARY KEY, sha1 TEXT NOT NULL, last_ingested_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP, parser_version INTEGER DEFAULT 1)"
        )

    def _is_unchanged(self, path: str, sha1: str) -> bool:
        row = self.conn.execute("SELECT sha1 FROM provenance WHERE path=?", (path,)).fetchone()
        return bool(row and row[0] == sha1)

    def _record_provenance(self, path: str, sha1: str):
        self.conn.execute(
            "INSERT INTO provenance(path, sha1, last_ingested_at) VALUES(?,?,CURRENT_TIMESTAMP) ON CONFLICT(path) DO UPDATE SET sha1=excluded.sha1, last_ingested_at=CURRENT_TIMESTAMP",
            (path, sha1),
        )

    @staticmethod
    def _derive_team_id(team_name: str) -> str:
        return team_name.lower().replace(" ", "-")

    @staticmethod
    def _derive_club_id(team_name: str) -> str:
        return team_name.split()[0].lower()

    @staticmethod
    def _split_club_and_suffix(full_team_name: str) -> tuple[str, str]:
        tokens = full_team_name.strip().split()
        if not tokens:
            return full_team_name, "1"

        def is_year(tok: str) -> bool:
            return tok.isdigit() and 1850 <= int(tok) <= 2099

        def is_team_num(tok: str) -> bool:
            return tok.isdigit() and 1 <= int(tok) <= 20

        if len(tokens) >= 2:
            last = tokens[-1]
            if is_team_num(last):
                # Common pattern: club name ends with a founding year followed by a team number
                # e.g. "LTTV Leutzscher Füchse 1990 7" -> club: "LTTV Leutzscher Füchse 1990" suffix: "7"
                # We treat the trailing number strictly as suffix and keep any prior year token inside club name.
                return " ".join(tokens[:-1]), last
            # If the string ends with a year we keep it within the club portion (no numeric suffix)
            if is_year(last):
                return full_team_name, "1"
        return full_team_name, "1"

    @staticmethod
    def _extract_numeric_id_from_path(path: str) -> str | None:
        import re, os

        fname = os.path.basename(path)
        m = re.search(r"_(\d+)\.html$", fname)
        return m.group(1) if m else None

    @staticmethod
    def _choose_canonical_name(variants: list[str]) -> str:
        if not variants:
            return "unknown-team"
        norm = [v.strip() for v in variants if v.strip()]
        if not norm:
            return variants[0]

        def score(name: str) -> tuple[int, int, int]:
            tokens = name.split()
            if not tokens:
                return (0, 0, 0)
            has_number_suffix = 1 if (tokens and any(ch.isdigit() for ch in tokens[-1])) else 0
            length = len(tokens)
            alpha_tokens = sum(1 for t in tokens if any(c.isalpha() for c in t))
            return (alpha_tokens, has_number_suffix, length)

        norm.sort(key=score, reverse=True)
        return norm[0]

    @staticmethod
    def _read_html(path: Path) -> str:
        try:
            return path.read_text(encoding="utf-8")
        except Exception:
            try:
                return path.read_bytes().decode("latin-1")
            except Exception:
                return path.read_text(errors="ignore")


class _IngestEventLogger:
    FILENAME = "ingest_events.jsonl"

    def __init__(self, path: Path):
        self._path = path

    @classmethod
    def try_create(cls, base_dir: Path):  # pragma: no cover
        from .service_locator import services

        enabled = True
        try:
            opt = services.try_get("ingest_event_logging")
            if opt is not None:
                enabled = bool(opt)
        except Exception:
            pass
        if not enabled:
            return None
        try:
            target = base_dir / cls.FILENAME
            if not target.exists():
                target.write_text("", encoding="utf-8")
            return cls(target)
        except Exception:
            return None

    def emit(self, event: str, payload: dict):  # pragma: no cover
        record = {"ts": time.time(), "event": event, **payload}
        try:
            with self._path.open("a", encoding="utf-8") as f:
                f.write(json.dumps(record, ensure_ascii=False) + "\n")
        except Exception:
            pass
