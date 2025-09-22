import os
import shutil
import sqlite3
from pathlib import Path

from db.schema import apply_schema
from gui.services.ingestion_coordinator import IngestionCoordinator
from gui.repositories.sqlite_impl import create_sqlite_repositories

DATA_SRC = Path("data") / "1_Bezirksliga_Erwachsene"
REQUIRED_FILES = [
    "ranking_table_1_Bezirksliga_Erwachsene.html",
    "team_roster_1_Bezirksliga_Erwachsene_TTC_Großpösna_1968_129451.html",
    "team_roster_1_Bezirksliga_Erwachsene_TTC_Großpösna_1968_2_129452.html",
    "team_roster_1_Bezirksliga_Erwachsene_LTTV_Leutzscher_Füchse_1990_3_128855.html",
    "team_roster_1_Bezirksliga_Erwachsene_LTTV_Leutzscher_Füchse_1990_2_128854.html",
]


def _prepare_subset(dst: Path):
    dst.mkdir(parents=True, exist_ok=True)
    for fname in REQUIRED_FILES:
        src_path = DATA_SRC / fname
        assert src_path.exists(), f"Missing source fixture {src_path}"
        shutil.copy2(src_path, dst / fname)


def test_team_suffix_and_livepz_parsing(tmp_path):
    # 1. Prepare minimal fixture directory
    target_div_dir = tmp_path / "1_Bezirksliga_Erwachsene"
    _prepare_subset(target_div_dir)

    # 2. Setup in-memory sqlite (apply singular schema)
    conn = sqlite3.connect(":memory:")
    apply_schema(conn)

    # 3. Run ingestion
    ic = IngestionCoordinator(base_dir=str(tmp_path), conn=conn)
    summary = ic.run()
    assert summary.teams_ingested >= 2, "Expected at least two teams ingested for club variants"

    # 4. Repositories
    repos = create_sqlite_repositories(conn)

    # 5. Validate TTC Großpösna 1968 club teams (suffix handling: founding year retained, suffix 1 implicit and 2 explicit)
    club_rows = conn.execute(
        "SELECT club_id, name FROM club WHERE name=?", ("TTC Großpösna 1968",)
    ).fetchall()
    assert club_rows, "Club TTC Großpösna 1968 not ingested"
    club_id = club_rows[0][0]
    team_rows = conn.execute(
        "SELECT name FROM team WHERE club_id=? ORDER BY name", (club_id,)
    ).fetchall()
    suffixes = {r[0] for r in team_rows}
    # Should contain '1' (implicit) and '2' (explicit second team)
    assert {"1", "2"}.issubset(suffixes), f"Missing expected suffixes, saw {suffixes}"

    # 6. Validate LTTV Leutzscher Füchse 1990 retains founding year and suffix parsed
    lttv_club = conn.execute(
        "SELECT club_id FROM club WHERE name=?", ("LTTV Leutzscher Füchse 1990",)
    ).fetchone()
    assert lttv_club, "Founding year 1990 should be part of club name"
    lttv_team_suffixes = {
        r[0]
        for r in conn.execute(
            "SELECT name FROM team WHERE club_id=? ORDER BY name", (lttv_club[0],)
        ).fetchall()
    }
    assert lttv_team_suffixes & {
        "2",
        "3",
    }, f"Expected at least one numbered team for LTTV, got {lttv_team_suffixes}"

    # 7. Pick TTC Großpösna 1968 first team and inspect players + live_pz
    team1_id = conn.execute(
        "SELECT team_id FROM team WHERE club_id=? AND name='1'", (club_id,)
    ).fetchone()[0]
    players = conn.execute(
        "SELECT full_name, live_pz FROM player WHERE team_id=? ORDER BY full_name", (team1_id,)
    ).fetchall()
    assert players, "Expected parsed players for TTC Großpösna 1968 first team"

    # Noise tokens we explicitly filter (lowercased comparison)
    noise = {"aktuelle tabelle", "allgemeine ligastatistiken"}
    cleaned = [p for p in players if p[0].strip().lower() not in noise]
    assert len(cleaned) == len(players), "Noise entries leaked into players"

    # At least one player should have a LivePZ rating > 500 (plausible rating)
    live_pz_values = [pz for _, pz in players if pz is not None]
    assert any(
        pz > 500 for pz in live_pz_values
    ), f"No plausible LivePZ values extracted: {live_pz_values}"

    # Player names should not contain navigation phrases
    forbidden_substrings = ["Tabelle", "Übersicht", "Allgemeine"]
    for name, _ in players:
        for sub in forbidden_substrings:
            assert sub.lower() not in name.lower(), f"Navigation noise leaked: {name}"
