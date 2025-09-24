import sqlite3, pathlib, tempfile, re
from db.ingest import ingest_path, incremental_refresh
from db.schema import apply_schema
from db.migration_manager import apply_pending_migrations
RANKING_HTML='<html><head><title>TischtennisLive - Division X - Tabelle</title></head><body><a>Teams</a><ul><li><a href=\'team1.html\'>T1</a><span>Team Alpha</span></li></ul></body></html>'
ROSTER_V1='<html><body><table><tr><td><a href=\'Spieler123\'>Alice</a></td><td class=\'tooltip\' title=\'LivePZ-Wert: 1500\'>1500</td></tr><tr><td><a href=\'Spieler456\'>Bob</a></td><td class=\'tooltip\' title=\'LivePZ-Wert: 1450\'>1450</td></tr></table></body></html>'
ROSTER_V2=ROSTER_V1.replace('1450','1460')
root=pathlib.Path(tempfile.mkdtemp())
(root/'ranking_table_division_x.html').write_text(RANKING_HTML, encoding='utf-8')
(root/'team_roster_division_x_Team_Alpha_1.html').write_text(ROSTER_V1, encoding='utf-8')
conn=sqlite3.connect(':memory:')
conn.execute('PRAGMA foreign_keys=ON')
apply_schema(conn); apply_pending_migrations(conn)
ingest_path(conn, root)
print('Initial:', list(conn.execute('select full_name, live_pz from player order by full_name')))
(root/'team_roster_division_x_Team_Alpha_1.html').write_text(ROSTER_V2, encoding='utf-8')
res=incremental_refresh(conn, root)
print('After roster change res:', res)
print('After roster change players:', list(conn.execute('select full_name, live_pz from player order by full_name')))
(root/'ranking_table_division_x.html').write_text(RANKING_HTML+'\n', encoding='utf-8')
res2=incremental_refresh(conn, root)
print('After ranking change res2:', res2)
print('After ranking change players:', list(conn.execute('select full_name, live_pz from player order by full_name')))
