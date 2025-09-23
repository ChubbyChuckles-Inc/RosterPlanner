import sqlite3, tempfile, pathlib, os, sys

# Ensure local 'src' package is importable when executing directly
SRC_PATH = pathlib.Path(__file__).resolve().parents[1] / "src"
if str(SRC_PATH) not in sys.path:
    sys.path.insert(0, str(SRC_PATH))

from db.schema import apply_schema
from db.migration_manager import apply_pending_migrations
from db.ingest import ingest_path, incremental_refresh

RANKING_HTML = """<html><head><title>TischtennisLive - Division X - Tabelle</title></head><body><a>Teams</a><ul><li><a href='team1.html'>T1</a><span>Team Alpha</span></li></ul></body></html>"""
ROSTER_HTML_V1 = """<html><body><table><tr><td><a href='Spieler123'>Alice</a></td><td class='tooltip' title='LivePZ-Wert: 1500'>1500</td></tr><tr><td><a href='Spieler456'>Bob</a></td><td class='tooltip' title='LivePZ-Wert: 1450'>1450</td></tr></table></body></html>"""


def main():
    with tempfile.TemporaryDirectory() as d:
        root = pathlib.Path(d)
        (root / "ranking_table_division_x.html").write_text(RANKING_HTML, "utf-8")
        (root / "team_roster_division_x_Team_Alpha_1.html").write_text(ROSTER_HTML_V1, "utf-8")
        conn = sqlite3.connect(":memory:")
        conn.execute("PRAGMA foreign_keys=ON")
        apply_schema(conn)
        apply_pending_migrations(conn)
        ingest_path(conn, root)
        cur = conn.cursor()
        cur.execute("SELECT source_file FROM ingest_provenance")
        rows = cur.fetchall()
        print("Provenance count", len(rows))
        for r in rows:
            print("PROV", os.path.basename(r[0]))
        res = incremental_refresh(conn, root)
        print("Incremental parsed_files", res.parsed_files, "skipped", res.skipped_unchanged)


if __name__ == "__main__":
    main()
