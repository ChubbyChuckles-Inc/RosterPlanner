from __future__ import annotations

import sqlite3
from pathlib import Path

from db.rebuild import rebuild_database
from db.schema import apply_schema
from db.migration_manager import apply_pending_migrations
from db.ingest import ingest_path

RANKING_HTML = """<html><head><title>TischtennisLive - Division Y - Tabelle</title></head>
<body>
<a>Teams</a>
<ul><li><a href=\"team1.html\">T1</a><span>Team Beta</span></li></ul>
</body></html>"""

ROSTER_HTML = """<html><body>
<table><tr><td><a href=\"Spieler999\">Charlie</a></td><td class=\"tooltip\" title=\"LivePZ-Wert: 1600\">1600</td></tr></table>
</body></html>"""


def _write(tmp_path: Path, name: str, content: str) -> Path:
    p = tmp_path / name
    p.write_text(content, encoding="utf-8")
    return p


def test_rebuild_drops_and_reingests(tmp_path: Path):
    # Prepare HTML files
    _write(tmp_path, "ranking_table_division_y.html", RANKING_HTML)
    _write(tmp_path, "team_roster_division_y_Team_Beta_1.html", ROSTER_HTML)

    conn = sqlite3.connect(":memory:")
    conn.execute("PRAGMA foreign_keys=ON")
    # Initial ingest using normal path to create tables & data
    apply_schema(conn)
    apply_pending_migrations(conn)
    ingest_path(conn, tmp_path)
    # Insert manual bogus row to be removed by rebuild (simulate drift)
    conn.execute("INSERT INTO player(team_id, full_name, live_pz) VALUES(9999, 'ZZZ', 0)")
    # Rebuild
    report = rebuild_database(conn, tmp_path)
    # Ensure bogus row removed: player_id referencing nonexistent team should not survive because tables were dropped
    cur = conn.cursor()
    cur.execute("SELECT COUNT(*) FROM player WHERE full_name='ZZZ'")
    assert cur.fetchone()[0] == 0
    # Ensure expected player exists post rebuild
    cur.execute("SELECT COUNT(*) FROM player WHERE full_name='Charlie'")
    assert cur.fetchone()[0] == 1
    assert report.total_players_inserted >= 1
