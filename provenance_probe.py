import sqlite3, tempfile
from pathlib import Path
from db.schema import apply_schema
from db.migration_manager import apply_pending_migrations
from db.ingest import ingest_path, incremental_refresh

RANKING_HTML = '<html><body><a>Teams</a><ul><li><a href="team1.html">T1</a><span>Team Alpha</span></li></ul></body></html>'
ROSTER_HTML = '<html><body><table><tr><td><a href="Spieler123">Alice</a></td><td class="tooltip" title="LivePZ-Wert: 1500">1500</td></tr><tr><td><a href="Spieler456">Bob</a></td><td class="tooltip" title="LivePZ-Wert: 1450">1450</td></tr></table></body></html>'

d = tempfile.mkdtemp()
p = Path(d)
(p / "ranking_table_division_x.html").write_text(RANKING_HTML, "utf-8")
(p / "team_roster_division_x_Team_Alpha_1.html").write_text(ROSTER_HTML, "utf-8")
conn = sqlite3.connect(":memory:")
conn.execute("PRAGMA foreign_keys=ON")
apply_schema(conn)
apply_pending_migrations(conn)
ingest_path(conn, p)
cur = conn.cursor()
cur.execute("select source_file, hash from ingest_provenance")
rows = cur.fetchall()
print("provenance count", len(rows))
for r in rows:
    print("prov", r[0])
cur.execute("select count(*) from player")
print("players", cur.fetchone()[0])
res = incremental_refresh(conn, p)
print("incremental", res.processed_files, res.skipped_unchanged, res.new_files, res.changed_files)
