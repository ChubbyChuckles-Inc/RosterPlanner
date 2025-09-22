"""Tests for ingest-only CLI (Milestone 5.9.21)."""

from __future__ import annotations

import json
from pathlib import Path

from cli import ingest_only


def _write(
    p: Path,
    name: str,
    content: str = "<html><table><tr><td>1</td><td>Team</td></tr></table></html>",
):
    p.mkdir(parents=True, exist_ok=True)
    (p / name).write_text(content, encoding="utf-8")


def _prepare_fixture(tmp_path: Path) -> Path:
    # Minimal division + two roster files (placeholders fine)
    _write(tmp_path, "ranking_table_Test_Division.html")
    _write(tmp_path, "team_roster_Test_Division_Sample_Club_1_101.html")
    _write(tmp_path, "team_roster_Test_Division_Sample_Club_2_202.html")
    return tmp_path


def test_ingest_only_cli_json(tmp_path, capsys):
    data_dir = _prepare_fixture(tmp_path / "data")
    db_path = tmp_path / "ingest.sqlite"
    code = ingest_only.main(
        [
            "--data-dir",
            str(data_dir),
            "--db",
            str(db_path),
            "--json",
        ]
    )
    captured = capsys.readouterr().out.strip()
    payload = json.loads(captured)
    assert code == 0
    assert payload["summary"]["divisions_ingested"] == 1
    assert payload["summary"]["teams_ingested"] == 2
    assert payload["consistency"]["clean"] is True
    assert db_path.exists()
