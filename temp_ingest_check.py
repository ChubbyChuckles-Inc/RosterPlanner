import sqlite3, sys, pathlib
sys.path.insert(0, str(pathlib.Path('src').resolve()))
from gui.services.ingestion_coordinator import IngestionCoordinator
from config import settings

conn = sqlite3.connect(':memory:')
conn.execute('CREATE TABLE division(division_id INTEGER PRIMARY KEY, name TEXT, season INTEGER)')
conn.execute('CREATE TABLE club(club_id INTEGER PRIMARY KEY, name TEXT)')
conn.execute('CREATE TABLE team(team_id INTEGER PRIMARY KEY, club_id INTEGER, division_id INTEGER, name TEXT)')
conn.execute('CREATE TABLE player(player_id INTEGER PRIMARY KEY, team_id INTEGER, full_name TEXT, live_pz INTEGER)')
coordinator = IngestionCoordinator(base_dir=settings.DATA_DIR, conn=conn)
summary = coordinator.run()
print('Summary divisions/teams/players:', summary.divisions_ingested, summary.teams_ingested, summary.players_ingested)
for div_id, name in conn.execute('SELECT division_id, name FROM division ORDER BY name'):
    count = conn.execute('SELECT COUNT(*) FROM team WHERE division_id=?',(div_id,)).fetchone()[0]
    print(f'Division {name} -> {count} teams')
