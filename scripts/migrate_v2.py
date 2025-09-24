"""Database migration to schema version 2.

Adds column `canonical_name` to `team` table and populates it with normalized
variants; also purges pre-existing duplicate teams (same division + canonical).

Safe to run multiple times (idempotent):
 - Adds column if missing
 - Creates helper index if absent
 - Performs a de-dup pass keeping the earliest (lowest team_id) row, merging
   players from duplicates into survivor, then deleting duplicates.

Usage (PowerShell):
  pwsh -File scripts/migrate_v2.ps1  # wrapper, or run directly:
  python -m scripts.migrate_v2 path/to/sqlite.db

If no path passed, attempts to locate a default `rosterplanner.db` in project root.
"""

from __future__ import annotations
import sys, sqlite3, os, re, unicodedata
from pathlib import Path


def norm_name(s: str) -> str:
    s2 = unicodedata.normalize("NFKD", s)
    s2 = "".join(c for c in s2 if not unicodedata.combining(c)).lower()
    s2 = s2.replace("-", " ").replace("_", " ")
    s2 = re.sub(r"[^a-z0-9 ]+", " ", s2)
    s2 = re.sub(r"\s+", " ", s2).strip()
    return s2


def ensure_column(conn: sqlite3.Connection):
    cur = conn.execute("PRAGMA table_info(team)")
    cols = {r[1] for r in cur.fetchall()}
    if "canonical_name" not in cols:
        conn.execute("ALTER TABLE team ADD COLUMN canonical_name TEXT")
    # index for faster lookup
    try:
        conn.execute(
            "CREATE INDEX IF NOT EXISTS idx_team_division_canonical ON team(division_id, canonical_name)"
        )
    except Exception:
        pass


def populate_canonical(conn: sqlite3.Connection):
    rows = conn.execute("SELECT team_id, name, canonical_name FROM team").fetchall()
    to_update = []
    for tid, name, c in rows:
        if not c:
            to_update.append((norm_name(name), tid))
    if to_update:
        conn.executemany("UPDATE team SET canonical_name=? WHERE team_id=?", to_update)


def dedupe(conn: sqlite3.Connection):
    # Find duplicates: same division + canonical_name
    dups = conn.execute(
        """
        SELECT division_id, canonical_name, COUNT(*) c
        FROM team
        WHERE canonical_name IS NOT NULL AND canonical_name<>''
        GROUP BY division_id, canonical_name
        HAVING c > 1
        """
    ).fetchall()
    for division_id, canonical_name, _ in dups:
        rows = conn.execute(
            "SELECT team_id, name FROM team WHERE division_id=? AND canonical_name=? ORDER BY team_id",
            (division_id, canonical_name),
        ).fetchall()
        if len(rows) < 2:
            continue
        survivor = rows[0][0]
        duplicates = [r[0] for r in rows[1:]]
        # Re-point players from duplicates
        conn.executemany(
            "UPDATE player SET team_id=? WHERE team_id=?",
            [(survivor, dup) for dup in duplicates],
        )
        # Delete duplicate teams
        conn.executemany("DELETE FROM team WHERE team_id=?", [(d,) for d in duplicates])


def main(argv: list[str]):
    if len(argv) > 1:
        db_path = Path(argv[1])
    else:
        # heuristic default paths
        candidates = [Path("rosterplanner.db"), Path("data") / "rosterplanner.db"]
        db_path = None
        for c in candidates:
            if c.exists():
                db_path = c
                break
        if db_path is None:
            print("No database path provided and no default found.")
            return 2
    conn = sqlite3.connect(str(db_path))
    try:
        ensure_column(conn)
        populate_canonical(conn)
        dedupe(conn)
        conn.commit()
        print("Migration to v2 canonical_name + dedupe complete.")
        return 0
    finally:
        conn.close()


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
