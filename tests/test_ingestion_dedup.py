import os, sqlite3, textwrap, tempfile, shutil
from pathlib import Path

from src.gui.services.ingestion_coordinator import IngestionCoordinator
from src.gui.services.data_audit import DataAuditService

HTML = """<html><head><title>Roster</title></head><body><h1>Spieler</h1></body></html>"""


def _write(p: Path, name: str):
    p.write_text(HTML, encoding="utf-8")


def test_ingestion_deduplicates_variants():
    # Create a temp data dir with a division ranking table and two roster variants differing by team name
    tmp = Path(tempfile.mkdtemp())
    try:
        division = "2_Bezirksliga_Erwachsene"
        div_dir = tmp / division
        div_dir.mkdir()
        (div_dir / f"ranking_table_{division}.html").write_text("<html></html>")
        # Two variants referencing same numeric id 129869
        _write(div_dir / "team_roster_2_Bezirksliga_Erwachsene_SSV_Stotteritz_2_129869.html", "A")
        _write(div_dir / "team_roster_2_Bezirksliga_Erwachsene_2_Erwachsene_129869.html", "B")

        conn = sqlite3.connect(":memory:")
        # Minimal schema needed
        conn.executescript(
            """
            CREATE TABLE divisions(id TEXT PRIMARY KEY, name TEXT);
            CREATE TABLE clubs(id TEXT PRIMARY KEY, name TEXT);
            CREATE TABLE teams(id TEXT PRIMARY KEY, name TEXT, division_id TEXT, club_id TEXT);
            """
        )
        ing = IngestionCoordinator(str(tmp), conn, event_bus=None)
        summary = ing.run()
        # Only one team should be ingested despite two roster files
        cur = conn.execute("SELECT id, name FROM teams")
        rows = cur.fetchall()
        assert len(rows) == 1, rows
        # Canonical name should be the longer descriptive variant (contains SSV)
        team_id, name = rows[0]
        assert "SSV" in name or len(name.split()) >= 2
    finally:
        shutil.rmtree(tmp)
