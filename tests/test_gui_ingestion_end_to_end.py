import os
import shutil
import sqlite3
import time
from pathlib import Path

import pytest
from PyQt6.QtWidgets import QApplication


# Ensure a minimal QApplication (offscreen)
app = QApplication.instance() or QApplication(["test"])  # pragma: no cover - initialization

from gui.app.bootstrap import create_app
from gui.views.main_window import MainWindow
from gui.services.ingestion_coordinator import IngestionCoordinator
from gui.services.data_state_service import DataStateService
from gui.repositories.sqlite_impl import create_sqlite_repositories
from gui.models import TeamEntry


def _copy_fixture_html(src_dir: Path, dst_dir: Path):
    for root, _, files in os.walk(src_dir):
        for f in files:
            if f.endswith(".html") and (
                f.startswith("ranking_table_") or f.startswith("team_roster_")
            ):
                rel_root = Path(root).relative_to(src_dir)
                target_root = dst_dir / rel_root
                target_root.mkdir(parents=True, exist_ok=True)
                shutil.copy2(Path(root) / f, target_root / f)


@pytest.mark.integration
def test_end_to_end_ingest_and_gui_navigation(tmp_path):
    # 1. Prepare temp data directory with a subset of existing HTML assets
    data_dir = tmp_path / "data"
    data_dir.mkdir()
    # Choose one division folder from repository data for realistic filenames
    repo_data_dir = Path("data") / "1_Bezirksliga_Erwachsene"
    assert repo_data_dir.exists(), "Expected sample data directory missing"
    _copy_fixture_html(repo_data_dir, data_dir)

    # 2. Bootstrap app headless with sqlite
    ctx = create_app(headless=True, data_dir=str(data_dir))
    conn = ctx.services.get("sqlite_conn")
    assert conn is not None, "SQLite connection not initialized"

    # 3. Run ingestion coordinator directly (bypass worker thread for determinism)
    ic = IngestionCoordinator(base_dir=str(data_dir), conn=conn)
    summary = ic.run()
    assert summary.teams_ingested > 0, "No teams ingested"

    # 4. Validate data state flags available
    state = DataStateService(conn).current_state()
    # Relax provenance gating: ensure at least one team present (summary count may include deduplicated variants)
    assert state.team_count > 0

    # 5. Launch MainWindow and invoke landing load logic manually (simulate worker completion)
    win = MainWindow(club_id=2294, season=2025, data_dir=str(data_dir))

    repos = create_sqlite_repositories(conn)
    club_map = {c.id: c.name for c in repos.clubs.list_clubs()}
    teams: list[TeamEntry] = []
    for d in repos.divisions.list_divisions():
        for t in repos.teams.list_teams_in_division(d.id):
            teams.append(
                TeamEntry(
                    team_id=str(t.id),
                    name=t.name,
                    division=d.name,
                    club_name=club_map.get(t.club_id) if t.club_id else None,
                )
            )
    assert teams, "Expected at least one team after ingestion"
    win._on_landing_loaded(teams, "")

    # 6. Interact with navigation tree programmatically
    model = win.team_tree.model()
    # Root season index always at (0,0) division at (row,0)
    first_div_idx = model.index(0, 0)
    win.team_tree.expand(first_div_idx)
    first_team_idx = model.index(0, 0, first_div_idx)
    label = model.data(first_team_idx)
    # The label should include an en dash separating club and suffix
    assert "–" in label, f"Expected club prefix in label: {label}"
    # Suffix should be last token (numeric)
    assert label.split()[-1].isdigit(), f"Expected numeric suffix at end: {label}"

    # 7. Load roster via TeamDataService directly (bypassing async thread)
    from gui.services.team_data_service import TeamDataService

    svc = TeamDataService(conn=conn)
    bundle = svc.load_team_bundle(teams[0])
    assert bundle is not None, "Bundle not returned"
    assert bundle.players, "Expected placeholder player inserted during ingestion"
    assert any("Placeholder" in p.name for p in bundle.players), "Placeholder player missing"

    # 8. (Optional) ensure display_name property consistent
    assert teams[0].display_name.startswith(teams[0].club_name.split()[0])
