from __future__ import annotations

import sqlite3
from pathlib import Path
import time

from db.schema import apply_schema
from db.migration_manager import apply_pending_migrations
from db.ingest import ingest_path, evict_stale_provenance, incremental_refresh

RANKING_HTML = """<html><head><title>TischtennisLive - Division X - Tabelle</title></head>
<body>
<a>Teams</a>
<ul><li><a href=\"team1.html\">T1</a><span>Team Alpha</span></li></ul>
</body></html>"""

ROSTER_HTML = """<html><body>
<table><tr><td><a href=\"Spieler123\">Alice</a></td><td class=\"tooltip\" title=\"LivePZ-Wert: 1500\">1500</td></tr>
<tr><td><a href=\"Spieler456\">Bob</a></td><td class=\"tooltip\" title=\"LivePZ-Wert: 1450\">1450</td></tr></table>
</body></html>"""


def _write(tmp_path: Path, name: str, content: str) -> Path:
    p = tmp_path / name
    p.write_text(content, encoding="utf-8")
    return p


def _bootstrap(conn: sqlite3.Connection):
    conn.execute("PRAGMA foreign_keys=ON")
    apply_schema(conn)
    apply_pending_migrations(conn)


def test_lru_eviction_by_max_entries(tmp_path: Path):
    conn = sqlite3.connect(":memory:")
    _bootstrap(conn)
    # Create multiple ranking/roster pairs to populate provenance
    for i in range(5):
        r_html = RANKING_HTML.replace("Division X", f"Division {i}").replace(
            "Team Alpha", f"Team Alpha {i}"
        )
        ranking = _write(tmp_path, f"ranking_table_division_{i}.html", r_html)
        roster = _write(tmp_path, f"team_roster_division_{i}_Team_Alpha_{i}.html", ROSTER_HTML)
    ingest_path(conn, tmp_path)
    # Access some files via incremental refresh to update last_accessed_at
    incremental_refresh(conn, tmp_path)
    # Evict keeping only 3 most recently accessed entries (rough heuristic since both ranking/roster inserted)
    res = evict_stale_provenance(conn, max_entries=3)
    assert res.removed > 0
    cur = conn.cursor()
    cur.execute("SELECT COUNT(*) FROM ingest_provenance")
    remaining = cur.fetchone()[0]
    assert remaining <= 3


def test_age_based_eviction(tmp_path: Path):
    conn = sqlite3.connect(":memory:")
    _bootstrap(conn)
    ranking = _write(tmp_path, "ranking_table_division_x.html", RANKING_HTML)
    roster = _write(tmp_path, "team_roster_division_x_Team_Alpha_1.html", ROSTER_HTML)
    ingest_path(conn, tmp_path)
    # Manually backdate last_accessed_at to simulate staleness
    try:
        conn.execute("UPDATE ingest_provenance SET last_accessed_at = datetime('now', '-10 days')")
    except sqlite3.OperationalError:
        # Column may not exist if migration failed; fallback to ingested_at
        conn.execute("UPDATE ingest_provenance SET ingested_at = datetime('now', '-10 days')")
    res = evict_stale_provenance(conn, max_age_days=5)
    assert res.removed > 0
    cur = conn.cursor()
    cur.execute("SELECT COUNT(*) FROM ingest_provenance")
    remaining = cur.fetchone()[0]
    assert remaining == 0
