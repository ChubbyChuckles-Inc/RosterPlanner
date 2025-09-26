"""Tests for snapshot_update CLI (Milestone 7.10.59).

Covers:
- Happy path generating snapshot file.
- Dry run mode not writing file.
- Error on missing inputs.
"""
from __future__ import annotations

import json, os, sys, types
from pathlib import Path

import pytest

from cli import snapshot_update as su
from gui.ingestion.rule_schema import RuleSet


@pytest.fixture()
def temp_rules_file(tmp_path: Path) -> Path:
    payload = {
        "version": 1,
        "resources": {
            "players": {
                "kind": "list",
                "selector": "ul.players",
                "item_selector": "li",
                "fields": {"name": {"selector": "li"}},
            }
        },
    }
    path = tmp_path / "rules.json"
    path.write_text(json.dumps(payload), encoding="utf-8")
    return path


@pytest.fixture()
def sample_html_files(tmp_path: Path) -> list[Path]:
    html = "<html><body><ul class='players'><li>Alice</li><li>Bob</li></ul></body></html>"
    files = []
    for i in range(2):
        p = tmp_path / f"sample{i}.html"
        p.write_text(html, encoding="utf-8")
        files.append(p)
    return files


def test_snapshot_update_happy_path(monkeypatch, tmp_path: Path, temp_rules_file: Path, sample_html_files):
    snap_dir = Path("tests/_extraction_snapshots")
    if snap_dir.exists():
        for f in snap_dir.glob("*.json"):
            f.unlink()
    argv = [
        "--rules",
        str(temp_rules_file),
        "--name",
        "players_baseline",
        "--input",
        *[str(p) for p in sample_html_files],
    ]
    rc = su.main(argv)
    assert rc == 0
    out = snap_dir / "players_baseline.json"
    assert out.exists()
    data = json.loads(out.read_text(encoding="utf-8"))
    assert data["resources"]["players"]["row_count"] == 2


def test_snapshot_update_dry_run(tmp_path: Path, temp_rules_file: Path, sample_html_files, capsys):
    argv = [
        "--rules",
        str(temp_rules_file),
        "--name",
        "players_dry",
        "--input",
        str(sample_html_files[0]),
        "--dry-run",
    ]
    rc = su.main(argv)
    assert rc == 0
    out = Path("tests/_extraction_snapshots/players_dry.json")
    assert not out.exists()
    captured = capsys.readouterr()
    assert "[DRY-RUN]" in captured.out


def test_snapshot_update_errors_on_no_inputs(tmp_path: Path, temp_rules_file: Path):
    # Provide a pattern that matches nothing to force error; we intercept SystemExit from argparse
    argv = ["--rules", str(temp_rules_file), "--name", "empty_case", "--input", "not_found_dir/*.html"]
    with pytest.raises(SystemExit):
        su.main(argv)
