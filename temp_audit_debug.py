import sys

sys.path.append("src")
from gui.services.data_audit import DataAuditService
from pathlib import Path
import shutil, os

base_repo = Path("data") / "1_Bezirksliga_Erwachsene"
assert base_repo.exists()

out = Path("temp_audit")
if out.exists():
    shutil.rmtree(out)
out.mkdir()
for root, _, files in os.walk(base_repo):
    for f in files:
        if f.endswith(".html") and (f.startswith("ranking_table_") or f.startswith("team_roster_")):
            rel = Path(root).relative_to(base_repo)
            dest = out / rel
            dest.mkdir(parents=True, exist_ok=True)
            shutil.copy2(Path(root) / f, dest / f)

result = DataAuditService(str(out)).run()
print("DIVISIONS", len(result.divisions))
for d in result.divisions:
    print("DIV", d.division, "ranking?", bool(d.ranking_table), "team_rosters", len(d.team_rosters))
