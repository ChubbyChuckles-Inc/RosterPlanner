from gui.services.ingestion_coordinator import IngestionCoordinator
import sqlite3, os, shutil
from pathlib import Path
from gui.services.migration_manager import MigrationManager

base_repo = Path("data") / "1_Bezirksliga_Erwachsene"
assert base_repo.exists(), "missing data folder"

tmp = Path("temp_ingest_test")
if tmp.exists():
    shutil.rmtree(tmp)
tmp.mkdir()
for root, _, files in os.walk(base_repo):
    for f in files:
        if f.endswith(".html") and (f.startswith("ranking_table_") or f.startswith("team_roster_")):
            rel = Path(root).relative_to(base_repo)
            dest = tmp / rel
            dest.mkdir(parents=True, exist_ok=True)
            shutil.copy2(Path(root) / f, dest / f)

conn = sqlite3.connect(":memory:")
MigrationManager(conn).apply_all()
ic = IngestionCoordinator(base_dir=str(tmp), conn=conn)
summary = ic.run()
print("SUMMARY", summary)
