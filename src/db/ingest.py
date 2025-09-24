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
import re
from typing import Dict, List, Tuple, Optional, Set

from parsing.ranking_parser import parse_ranking_table
from parsing.roster_parser import extract_players


PARSER_VERSION_DEFAULT = "v1"


# --- Roster File Indexing Helpers -------------------------------------------------------------

_ROSTER_ID_RE = re.compile(r"_(\d+)\.html$")


def hash_html(content: str) -> str:
    """Return SHA256 hex digest of raw HTML content."""
    return hashlib.sha256(content.encode("utf-8")).hexdigest()


def _normalize_slug(name: str) -> str:
    """Return a normalized slug for matching team names to roster file stems.

    Normalization steps:
      * lower-case
      * replace spaces & hyphen-like dashes with underscore
      * remove characters other than a-z, 0-9, underscore, umlaut letters collapsed
      * collapse multiple underscores
    (Umlauts retained as-is so that filenames containing them still match; further mapping can be
    added if upstream variation appears.)
    """
    s = name.strip().lower()
    s = re.sub(r"[\u2013\u2014\-\s]+", "_", s)  # hyphen-like + whitespace -> _
    s = re.sub(r"[^a-z0-9_äöüß]", "", s)
    s = re.sub(r"_+", "_", s).strip("_")
    return s


def _extract_club_and_team_from_title(html: str) -> Optional[Tuple[str, str]]:
    """Extract (club_name, team_designation) from roster HTML <title>.

    Expected pattern tail: ' - Team <Club Name>, <Team Designation>'
    Returns None if pattern not found or malformed.
    """
    m = re.search(r" - Team ([^,<]+?),\s*([^<]+)</title>", html, re.IGNORECASE)
    if not m:
        # Fallback: parse via simpler split if direct regex fails
        # Locate ' - Team ' then split on first comma
        idx = html.lower().rfind(" - team ")
        if idx == -1:
            return None
        after = html[idx + len(" - team "):]
        # up to closing title or first '</title>'
        end_idx = after.lower().find("</title>")
        if end_idx != -1:
            after = after[:end_idx]
        parts = after.split(",", 1)
        if len(parts) != 2:
            return None
        club = parts[0].strip()
        team = parts[1].strip()
        if club and team:
            return club, team
        return None
    club = m.group(1).strip()
    team = m.group(2).strip()
    if club and team:
        return club, team
    return None


@dataclass
class _RosterIndexEntry:
    path: Path
    team_id: Optional[str]
    slug: str


def _build_roster_index(root: Path) -> Dict[str, Dict[str, _RosterIndexEntry]]:
    """Index roster files by division folder with id and slug lookups."""
    index: Dict[str, Dict[str, Dict[str, _RosterIndexEntry]]] = {}
    for p in root.rglob("team_roster_*.html"):
        if not p.is_file():
            continue
        division_folder = p.parent.name
        fname = p.name
        m_id = _ROSTER_ID_RE.search(fname)
        team_id: Optional[str] = m_id.group(1) if m_id else None
        slug_part = fname[len("team_roster_"):] if fname.startswith("team_roster_") else fname
        if slug_part.lower().endswith(".html"):
            slug_part = slug_part[:-5]
        if m_id:
            slug_part = re.sub(r"_\d+$", "", slug_part)
        tokens = [t for t in slug_part.split("_") if t]
        bucket = index.setdefault(division_folder, {"by_id": {}, "by_slug": {}})
        for start in range(len(tokens)):
            cand = "_".join(tokens[start:])
            norm = _normalize_slug(cand)
            if not norm:
                continue
            entry = _RosterIndexEntry(path=p, team_id=team_id, slug=norm)
            if team_id:
                existing = bucket["by_id"].get(team_id)
                def quality(e: _RosterIndexEntry) -> tuple[int, int]:
                    return (0 if re.match(r"^\d+_", e.slug) else 1, len(e.slug))
                if (existing is None) or quality(entry) > quality(existing):
                    bucket["by_id"][team_id] = entry
            if norm not in bucket["by_slug"]:
                bucket["by_slug"][norm] = entry
    return {k: {"by_id": v["by_id"], "by_slug": v["by_slug"]} for k, v in index.items()}


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
    try:
        cur.execute(
            "SELECT 1 FROM ingest_provenance WHERE source_file=? AND hash=?",
            (source_file, file_hash),
        )
        return cur.fetchone() is not None
    except sqlite3.OperationalError:
        # Table not yet created (earlier schema or migration missing) – treat as absent.
        return False


def _record_provenance(
    conn: sqlite3.Connection, source_file: str, parser_version: str, file_hash: str
) -> None:
    try:
        conn.execute(
            "INSERT OR IGNORE INTO ingest_provenance(source_file, parser_version, hash) VALUES (?,?,?)",
            (source_file, parser_version, file_hash),
        )
    except sqlite3.OperationalError:
        # Gracefully ignore if table missing
        pass


def _touch_provenance(conn: sqlite3.Connection, source_file: str) -> None:
    """Update last_accessed_at & access_count for a provenance row if columns exist.

    Silently no-ops if migration adding those columns not yet applied.
    """
    try:
        conn.execute(
            "UPDATE ingest_provenance SET last_accessed_at=CURRENT_TIMESTAMP, access_count=COALESCE(access_count,0)+1 WHERE source_file=?",
            (source_file,),
        )
    except sqlite3.OperationalError:
        pass


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
    """Ingest ranking & roster HTML files.

    Strategy (revised):
      1. Parse each ranking file to establish division and capture canonical team display names.
      2. Independently index roster files per division folder; treat each unique roster id (numeric suffix) as one team.
      3. For each roster file, choose a human-friendly name:
           * If a ranking table slug matches, reuse that name.
           * Else synthesize from slug tokens (title case) to avoid deficits.
      4. Upsert team + players; provenance recorded for ranking + roster files.
    This guarantees ingested team count equals unique roster file ids per division, removing both deficits and surpluses
    caused by placeholder numeric-leading names or duplicate navigation entries.
    """
    root = Path(root_path)
    report = IngestReport()
    ranking_files = list(root.rglob("ranking_table_*.html"))
    roster_index = _build_roster_index(root)
    processed_roster_paths: Set[Path] = set()

    for ranking in ranking_files:
        content = ranking.read_text(encoding="utf-8", errors="ignore")
        file_hash = hash_html(content)
        result = FileIngestResult(source_file=str(ranking), hash=file_hash, skipped_unchanged=False)
        division_name, team_entries = parse_ranking_table(content, source_hint=ranking.name)
        previously_seen = _provenance_exists(conn, str(ranking), file_hash)
        if previously_seen:
            result.skipped_unchanged = True
        # Build slug -> display name map from ranking
        ranking_slug_map: Dict[str, str] = {}
        for t in team_entries:
            n = t.get("team_name")
            if n:
                ranking_slug_map[_normalize_slug(n)] = n
        with conn:
            div_id = _upsert_division(conn, division_name)
            if not previously_seen:
                for display in set(ranking_slug_map.values()):
                    _upsert_team(conn, div_id, display)
                _record_provenance(conn, str(ranking), parser_version, file_hash)
        division_folder = ranking.parent.name
        div_rosters = roster_index.get(division_folder, {"by_id": {}, "by_slug": {}})
        # Ingest each roster file exactly once
        for team_ext_id, entry in div_rosters.get("by_id", {}).items():
            if entry.path in processed_roster_paths:
                continue
            processed_roster_paths.add(entry.path)
            slug = entry.slug
            # Prefer ranking display name; else synthesize
            display_name = ranking_slug_map.get(slug)
            if not display_name:
                display_name = re.sub(r"\s+", " ", slug.replace("_", " ").strip()).title()
            roster_html = entry.path.read_text(encoding="utf-8", errors="ignore")
            # Attempt title-based extraction for club + team designation
            club_team = _extract_club_and_team_from_title(roster_html)
            combined_name = display_name
            original_ranking_name = display_name
            if club_team:
                club_name, team_designation = club_team
                # Build combined formatted name
                combined_name = f"{club_name} | {team_designation}"
            # If combined differs, try to UPDATE existing ranking-named row to avoid duplicates
            team_db_id: int
            if combined_name != original_ranking_name:
                cur = conn.cursor()
                cur.execute(
                    "SELECT team_id FROM team WHERE division_id=? AND name=?",
                    (div_id, original_ranking_name),
                )
                row = cur.fetchone()
                if row:
                    # Ensure no existing row already has combined_name
                    cur.execute(
                        "SELECT 1 FROM team WHERE division_id=? AND name=?",
                        (div_id, combined_name),
                    )
                    if cur.fetchone() is None:
                        cur.execute(
                            "UPDATE team SET name=? WHERE team_id=?",
                            (combined_name, row[0]),
                        )
                        team_db_id = int(row[0])
                    else:
                        team_db_id = _upsert_team(conn, div_id, combined_name)
                else:
                    team_db_id = _upsert_team(conn, div_id, combined_name)
            else:
                team_db_id = _upsert_team(conn, div_id, combined_name)
            roster_hash = hash_html(roster_html)
            existing = _provenance_exists(conn, str(entry.path), roster_hash)
            players = extract_players(roster_html, team_id=str(team_db_id))
            inserted = updated = 0
            for p in players:
                ins, upd = _upsert_player(conn, team_db_id, p.name, p.live_pz)
                if ins:
                    inserted += 1
                if upd:
                    updated += 1
            if players:
                result.inserted_players += inserted
                result.updated_players += updated
            if not existing:
                _record_provenance(conn, str(entry.path), parser_version, roster_hash)
        report.files.append(result)
    return report


__all__ = [
    "ingest_path",
    "hash_html",
    "IngestReport",
    "FileIngestResult",
    "incremental_refresh",
    "IncrementalRefreshResult",
    "evict_stale_provenance",
    "EvictionResult",
]


# --- Incremental Refresh (Milestone 3.7) -------------------------------------------------------


@dataclass
class IncrementalRefreshResult:
    """Result summary for `incremental_refresh`.

    Attributes:
        processed_files: Count of files whose hashes were evaluated (ranking + roster).
        parsed_files: Files actually parsed this run (new or changed).
        skipped_unchanged: Files skipped because hash matched existing provenance.
        new_files: Newly discovered files with no prior provenance row.
        changed_files: Previously seen source files whose content hash changed, triggering re-parse.
        inserted_players: Aggregate inserted player rows (from underlying ingest logic).
        updated_players: Aggregate updated player rows.
        errors: Mapping of source_file -> error string for any failures while parsing/upserting. Errors do not stop the overall refresh unless critical (future enhancement: severity classification).
    """

    processed_files: int = 0
    parsed_files: int = 0
    skipped_unchanged: int = 0
    new_files: int = 0
    changed_files: int = 0
    inserted_players: int = 0
    updated_players: int = 0
    errors: Dict[str, str] = field(default_factory=dict)


def incremental_refresh(
    conn: sqlite3.Connection,
    root_path: str | Path,
    parser_version: str = PARSER_VERSION_DEFAULT,
) -> IncrementalRefreshResult:
    """Perform an incremental refresh of HTML assets under `root_path`.

    This function scans ranking and roster HTML files (same patterns as `ingest_path`) and
    selects only those whose content hash is new or changed relative to the `ingest_provenance` table.

    Strategy:
        1. Enumerate candidate files (ranking_table_*.html + team_roster_*.html).
        2. Compute hash for each and classify into buckets: new / unchanged / changed.
           (Changed currently means: same source_file exists with different hash value recorded.)
        3. For ranking files deemed new or changed, perform a focused ingest similar to `ingest_path` but
           limiting roster parsing to roster files in the new/changed set (or roster files referenced that are themselves new/changed).
        4. Record provenance only after successful parsing/upsert.

    Returns a summary object with counts. Errors for individual files are captured; a failure does not abort
    other file processing (best-effort incremental semantics).

    NOTE: Implementation TBD in subsequent step (Milestone 3.7). Currently returns an empty result placeholder.
    """
    root = Path(root_path)
    result = IncrementalRefreshResult()

    ranking_files = list(root.rglob("ranking_table_*.html"))
    roster_files = list(root.rglob("team_roster_*.html"))

    # Build provenance map: source_file -> hash (latest). We assume (source_file, hash) uniqueness, so we fetch latest by insertion order.
    prov_cur = conn.cursor()
    prov_cur.execute("SELECT source_file, hash FROM ingest_provenance")
    provenance: Dict[str, str] = {}
    for full, h in prov_cur.fetchall():
        provenance[full] = h
        try:
            base = Path(full).name
            provenance.setdefault(base, h)
        except Exception:  # pragma: no cover
            pass

    # Helper classification
    def classify_file(path: Path) -> tuple[str, str]:
        try:
            content = path.read_text(encoding="utf-8", errors="ignore")
        except Exception as e:  # capture IO errors
            result.errors[str(path)] = f"read_error: {e}"  # will count as processed but not parsed
            return "error", ""
        file_hash = hash_html(content)
        prior = provenance.get(str(path))
        if prior is None:
            prior = provenance.get(path.name)
        if prior is None:
            return "new", file_hash
        if prior == file_hash:
            return "unchanged", file_hash
        return "changed", file_hash

    # Classify ranking + roster files
    ranking_meta: Dict[str, tuple[Path, str, str]] = {}  # path -> (path, status, hash)
    for rf in ranking_files:
        status, h = classify_file(rf)
        if status != "error":
            ranking_meta[str(rf)] = (rf, status, h)
            result.processed_files += 1
            if status == "unchanged":
                result.skipped_unchanged += 1
            elif status == "new":
                result.new_files += 1
            elif status == "changed":
                result.changed_files += 1

    roster_meta: Dict[str, tuple[Path, str, str]] = {}
    for tf in roster_files:
        status, h = classify_file(tf)
        if status != "error":
            roster_meta[str(tf)] = (tf, status, h)
            result.processed_files += 1
            if status == "unchanged":
                result.skipped_unchanged += 1
            elif status == "new":
                result.new_files += 1
            elif status == "changed":
                result.changed_files += 1

    # Heuristic: If roster classified as 'new' but players table already populated, treat as unchanged.
    # This handles scenarios where a prior full ingest populated players but failed to record roster provenance.
    if any(status == "new" for (_p, status, _h) in roster_meta.values()):
        try:
            cur = conn.cursor()
            cur.execute("SELECT 1 FROM player LIMIT 1")
            has_players = cur.fetchone() is not None
        except Exception:
            has_players = False
        if has_players:
            adjusted_keys = []
            for key, (p, status, h) in roster_meta.items():
                if status == "new":
                    # Update counts: transfer from new -> skipped_unchanged
                    if result.new_files > 0:
                        result.new_files -= 1
                    result.skipped_unchanged += 1
                    roster_meta[key] = (p, "unchanged", h)
                    adjusted_keys.append(key)

    # Parse only ranking files that are new/changed
    for path_str, (ranking_path, status, file_hash) in ranking_meta.items():
        if status not in {"new", "changed"}:
            _touch_provenance(conn, path_str)
            continue
        try:
            content = ranking_path.read_text(encoding="utf-8", errors="ignore")
            division_name, team_entries = parse_ranking_table(
                content, source_hint=ranking_path.name
            )
        except Exception as e:  # parsing error
            result.errors[path_str] = f"parse_error: {e}"
            continue
        # Ingest division + teams + related roster files limited to those new/changed
        with conn:
            try:
                div_id = _upsert_division(conn, division_name)
                for t in team_entries:
                    team_name = t.get("team_name")
                    if not team_name:
                        continue
                    team_id = _upsert_team(conn, div_id, team_name)
                    # Find candidate roster files containing normalized team name
                    normalized = team_name.replace(" ", "_")
                    for meta in roster_meta.values():
                        roster_path, r_status, roster_hash = meta
                        if r_status not in {"new", "changed"}:
                            _touch_provenance(conn, str(roster_path))
                            continue
                        if normalized not in roster_path.name:
                            continue
                        try:
                            roster_html = roster_path.read_text(encoding="utf-8", errors="ignore")
                            players = extract_players(roster_html, team_id=str(team_id))
                        except Exception as e:
                            result.errors[str(roster_path)] = f"roster_parse_error: {e}"
                            continue
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
                        # Record roster provenance only after success
                        _record_provenance(conn, str(roster_path), parser_version, roster_hash)
                        _touch_provenance(conn, str(roster_path))
                # Record provenance for ranking file after success
                _record_provenance(conn, path_str, parser_version, file_hash)
                _touch_provenance(conn, path_str)
                result.parsed_files += 1
            except Exception as e:  # capture any DB/upsert errors per file
                result.errors[path_str] = f"ingest_error: {e}"
                # Let transaction rollback automatically; continue with next file
                continue

    return result


# --- Eviction Policy (Milestone 3.7.1) ----------------------------------------------------------


@dataclass
class EvictionResult:
    inspected: int = 0
    removed: int = 0
    reason_counts: Dict[str, int] = field(default_factory=dict)


def evict_stale_provenance(
    conn: sqlite3.Connection,
    max_entries: int | None = None,
    max_age_days: int | None = None,
) -> EvictionResult:
    """Evict stale provenance rows via LRU (size) and/or age policy.

    Order of operations:
      1. Age-based deletions (rows older than NOW - max_age_days).
      2. Size-based deletions if total still exceeds max_entries.

    LRU ordering uses (last_accessed_at ASC, access_count ASC) when available; falls back to ingested_at.
    """
    res = EvictionResult()
    cur = conn.cursor()
    cur.execute("SELECT COUNT(*) FROM ingest_provenance")
    total = cur.fetchone()[0]
    res.inspected = int(total)

    # Age policy
    if max_age_days is not None:
        try:
            cur.execute(
                "DELETE FROM ingest_provenance WHERE last_accessed_at < datetime('now', ?)",
                (f"-{int(max_age_days)} days",),
            )
        except sqlite3.OperationalError:
            cur.execute(
                "DELETE FROM ingest_provenance WHERE ingested_at < datetime('now', ?)",
                (f"-{int(max_age_days)} days",),
            )
        deleted = cur.rowcount or 0
        if deleted:
            res.removed += deleted
            res.reason_counts["age"] = res.reason_counts.get("age", 0) + deleted

    # Size policy
    if max_entries is not None:
        cur.execute("SELECT COUNT(*) FROM ingest_provenance")
        count_after_age = cur.fetchone()[0]
        if count_after_age > max_entries:
            excess = count_after_age - max_entries
            try:
                cur.execute(
                    "SELECT provenance_id FROM ingest_provenance ORDER BY last_accessed_at ASC, access_count ASC LIMIT ?",
                    (excess,),
                )
            except sqlite3.OperationalError:
                cur.execute(
                    "SELECT provenance_id FROM ingest_provenance ORDER BY ingested_at ASC LIMIT ?",
                    (excess,),
                )
            victims = [r[0] for r in cur.fetchall()]
            if victims:
                cur.execute(
                    f"DELETE FROM ingest_provenance WHERE provenance_id IN ({','.join(['?']*len(victims))})",
                    victims,
                )
                deleted = cur.rowcount or len(victims)
                res.removed += deleted
                res.reason_counts["lru"] = res.reason_counts.get("lru", 0) + deleted

    conn.commit()
    return res
