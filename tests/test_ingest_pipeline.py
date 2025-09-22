from __future__ import annotations

import sqlite3
from pathlib import Path

from db.schema import apply_schema
from db.migration_manager import apply_pending_migrations
from db.ingest import ingest_path, hash_html


def _make_temp_html(tmp_path: Path, name: str, content: str) -> Path:
    p = tmp_path / name
    p.write_text(content, encoding="utf-8")
    return p


RANKING_HTML = """<html><head><title>TischtennisLive - Division X - Tabelle</title></head>
<body>
<a>Teams</a>
<ul><li><a href="team1.html">T1</a><span>Team Alpha</span></li></ul>
</body></html>"""

ROSTER_HTML = """<html><body>
<table><tr><td><a href="Spieler123">Alice</a></td><td class="tooltip" title="LivePZ-Wert: 1500">1500</td></tr>
<tr><td><a href="Spieler456">Bob</a></td><td class="tooltip" title="LivePZ-Wert: 1450">1450</td></tr></table>
</body></html>"""


def test_first_ingest_populates_players(tmp_path: Path):
    ranking = _make_temp_html(tmp_path, "ranking_table_division_x.html", RANKING_HTML)
    roster = _make_temp_html(tmp_path, "team_roster_division_x_Team_Alpha_1.html", ROSTER_HTML)
    conn = sqlite3.connect(":memory:")
    conn.execute("PRAGMA foreign_keys=ON")
    apply_schema(conn)
    apply_pending_migrations(conn)
    report = ingest_path(conn, tmp_path)
    assert report.total_players_inserted == 2
    assert report.total_players_updated == 0
    # Second run should skip both files
    report2 = ingest_path(conn, tmp_path)
    assert report2.files_skipped >= 1  # ranking at least


def test_modifying_roster_triggers_update(tmp_path: Path):
    ranking = _make_temp_html(tmp_path, "ranking_table_division_x.html", RANKING_HTML)
    roster = _make_temp_html(tmp_path, "team_roster_division_x_Team_Alpha_1.html", ROSTER_HTML)
    conn = sqlite3.connect(":memory:")
    conn.execute("PRAGMA foreign_keys=ON")
    apply_schema(conn)
    apply_pending_migrations(conn)
    ingest_path(conn, tmp_path)
    # Modify roster (change Bob's LivePZ)
    roster.write_text(ROSTER_HTML.replace("1450", "1460"), encoding="utf-8")
    report = ingest_path(conn, tmp_path)
    # One player updated
    assert report.total_players_updated >= 1
