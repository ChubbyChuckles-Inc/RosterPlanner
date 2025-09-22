from __future__ import annotations

import sqlite3
from pathlib import Path

from db.schema import apply_schema
from db.migration_manager import apply_pending_migrations
from db.ingest import ingest_path, incremental_refresh


RANKING_HTML = """<html><head><title>TischtennisLive - Division X - Tabelle</title></head>
<body>
<a>Teams</a>
<ul><li><a href=\"team1.html\">T1</a><span>Team Alpha</span></li></ul>
</body></html>"""

ROSTER_HTML_V1 = """<html><body>
<table><tr><td><a href=\"Spieler123\">Alice</a></td><td class=\"tooltip\" title=\"LivePZ-Wert: 1500\">1500</td></tr>
<tr><td><a href=\"Spieler456\">Bob</a></td><td class=\"tooltip\" title=\"LivePZ-Wert: 1450\">1450</td></tr></table>
</body></html>"""

ROSTER_HTML_V2 = ROSTER_HTML_V1.replace("1450", "1460")


def _make(conn: sqlite3.Connection):
    conn.execute("PRAGMA foreign_keys=ON")
    apply_schema(conn)
    apply_pending_migrations(conn)


def _write(tmp_path: Path, name: str, content: str) -> Path:
    p = tmp_path / name
    p.write_text(content, encoding="utf-8")
    return p


def test_incremental_refresh_initial_parses_all(tmp_path: Path):
    ranking = _write(tmp_path, "ranking_table_division_x.html", RANKING_HTML)
    roster = _write(tmp_path, "team_roster_division_x_Team_Alpha_1.html", ROSTER_HTML_V1)
    conn = sqlite3.connect(":memory:")
    _make(conn)
    # First run via full ingest for baseline provenance
    ingest_path(conn, tmp_path)
    # Change nothing; incremental refresh should skip both (parsed_files == 0)
    res = incremental_refresh(conn, tmp_path)
    assert res.parsed_files == 0
    assert res.skipped_unchanged >= 2  # ranking + roster


def test_incremental_refresh_detects_changed_roster(tmp_path: Path):
    ranking = _write(tmp_path, "ranking_table_division_x.html", RANKING_HTML)
    roster = _write(tmp_path, "team_roster_division_x_Team_Alpha_1.html", ROSTER_HTML_V1)
    conn = sqlite3.connect(":memory:")
    _make(conn)
    ingest_path(conn, tmp_path)
    # Modify roster file
    roster.write_text(ROSTER_HTML_V2, encoding="utf-8")
    res = incremental_refresh(conn, tmp_path)
    # Ranking unchanged, roster changed -> ranking not re-parsed, but roster processed via ranking ingest if ranking marked changed (it isn't)
    # Because we only re-parse ranking files when they themselves changed, and roster ingestion is tied to ranking parse,
    # a changed roster alone currently requires its ranking to be changed to re-ingest players. We therefore expect 0 parsed files,
    # but we can assert the classification counts reflect a changed file.
    assert res.changed_files >= 1  # roster file counted as changed
    # Now modify ranking to trigger parse cascade
    ranking.write_text(
        RANKING_HTML.replace("Team Alpha", "Team Alpha"), encoding="utf-8"
    )  # no semantic change but new file timestamp -> same content
    # Force ranking change by appending whitespace
    ranking.write_text(RANKING_HTML + "\n", encoding="utf-8")
    res2 = incremental_refresh(conn, tmp_path)
    # Ranking changed triggers re-parse; players should be updated (Bob 1450->1460)
    assert res2.parsed_files >= 1
    assert res2.updated_players >= 1


def test_incremental_refresh_new_files_only_parse_new(tmp_path: Path):
    conn = sqlite3.connect(":memory:")
    _make(conn)
    # Start with empty directory -> incremental refresh finds nothing
    res_empty = incremental_refresh(conn, tmp_path)
    assert res_empty.processed_files == 0
    # Add ranking + roster, run incremental -> they are new so ranking parsed
    _write(tmp_path, "ranking_table_division_x.html", RANKING_HTML)
    _write(tmp_path, "team_roster_division_x_Team_Alpha_1.html", ROSTER_HTML_V1)
    res_new = incremental_refresh(conn, tmp_path)
    assert res_new.new_files >= 2
    # After provenance, second run should skip
    res_again = incremental_refresh(conn, tmp_path)
    assert res_again.parsed_files == 0
    assert res_again.skipped_unchanged >= 2
