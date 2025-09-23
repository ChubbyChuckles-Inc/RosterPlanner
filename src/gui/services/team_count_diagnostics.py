"""Team Count Diagnostics

Provides utilities to compare the number of teams currently ingested/displayed
in the database with the number of roster HTML files present per division
subfolder in the data directory.

Heuristics:
  * Division folder names use underscores; DB division names use spaces.
  * Roster files follow pattern: team_roster_<division_name>_<team_name>_<numericid>.html
  * We derive a team key primarily from the trailing numeric id; if absent we
    fall back to the portion between division name and numeric id.
  * We compute both raw file count and unique team id count. The latter is used
    for expected team count (avoids double-counting if multiple variants exist).

Outputs a list of dict entries plus (optionally) writes JSON to a diagnostics
file for offline inspection.
"""

from __future__ import annotations

from dataclasses import dataclass, asdict
from pathlib import Path
import json
import re
import sqlite3
from typing import Iterable, List, Dict, Any

__all__ = [
    "DivisionTeamDiagnostic",
    "collect_team_file_stats",
    "collect_ingested_team_counts",
    "compare_team_counts",
]


@dataclass
class DivisionTeamDiagnostic:
    division_folder: str
    division_name: str
    ingested_count: int
    roster_file_count: int
    unique_roster_ids: int
    expected_count: int
    deficit: int
    surplus: int
    sample_files: list[str]

    def to_dict(self) -> Dict[str, Any]:  # convenience
        return asdict(self)


ROSTER_FILE_RE = re.compile(r"^team_roster_(?P<div>.+)_(?P<rest>.+?)_(?P<id>\d+)\.html$")


def _normalize_division_folder(name: str) -> str:
    return name.strip().rstrip("/")


def _folder_to_division_name(folder: str) -> str:
    return folder.replace("_", " ")


def collect_team_file_stats(base_dir: str) -> Dict[str, Dict[str, Any]]:
    """Walk division subfolders and gather roster file statistics.

    Returns mapping: division_folder -> { 'division_name': ..., 'roster_files': [...],
        'unique_ids': set(...), 'raw_count': N }
    """

    root = Path(base_dir)
    stats: Dict[str, Dict[str, Any]] = {}
    if not root.exists():  # pragma: no cover - defensive
        return stats
    for child in root.iterdir():
        if not child.is_dir():
            continue
        # Heuristic: treat as division folder if it contains at least one ranking or roster file
        roster_files = list(child.glob("team_roster_*.html"))
        ranking_files = list(child.glob("ranking_table_*.html"))
        if not roster_files and not ranking_files:
            continue
        folder_key = _normalize_division_folder(child.name)
        unique_ids = set()
        for rf in roster_files:
            m = ROSTER_FILE_RE.match(rf.name)
            if m:
                # Filter out generic files with purely numeric pseudo-team names like '1_Erwachsene'
                rest = m.group("rest")
                # Heuristic: skip if rest starts with a number followed by '_' (e.g., '1_Erwachsene')
                if re.match(r"^\d+_", rest):
                    continue
                unique_ids.add(m.group("id"))
            else:  # fallback: use filename minus prefix & suffix
                stem = rf.stem.replace("team_roster_", "")
                unique_ids.add(stem)
        stats[folder_key] = {
            "division_name": _folder_to_division_name(folder_key),
            "roster_files": [
                r.name
                for r in roster_files
                if not (
                    ROSTER_FILE_RE.match(r.name)
                    and re.match(r"^\d+_", ROSTER_FILE_RE.match(r.name).group("rest"))
                )
            ],
            "unique_ids": unique_ids,
            "raw_count": len(unique_ids),
        }
    return stats


def collect_ingested_team_counts(conn: sqlite3.Connection) -> Dict[str, int]:
    """Return mapping of division name -> ingested team count.

    Supports both singular (division/team) and legacy plural (divisions/teams) schemas.
    """
    cur = conn.execute("SELECT name FROM sqlite_master WHERE type='table'")
    tables = {r[0] for r in cur.fetchall()}
    result: Dict[str, int] = {}
    try:
        if "division" in tables and "team" in tables:
            sql = (
                "SELECT d.name, COUNT(t.team_id) FROM division d "
                "LEFT JOIN team t ON t.division_id=d.division_id GROUP BY d.name"
            )
            for name, cnt in conn.execute(sql):
                result[str(name)] = int(cnt)
        elif "divisions" in tables and "teams" in tables:
            sql = (
                "SELECT d.name, COUNT(t.id) FROM divisions d "
                "LEFT JOIN teams t ON t.division_id=d.id GROUP BY d.name"
            )
            for name, cnt in conn.execute(sql):
                result[str(name)] = int(cnt)
    except Exception:  # pragma: no cover - non-fatal
        pass
    return result


def compare_team_counts(
    base_dir: str,
    conn: sqlite3.Connection,
    *,
    write_json: bool = True,
    expected_adjustment: int = 0,
):
    file_stats = collect_team_file_stats(base_dir)
    ingested = collect_ingested_team_counts(conn)
    diagnostics: List[DivisionTeamDiagnostic] = []
    for folder, info in sorted(file_stats.items()):
        div_name = info["division_name"]
        roster_file_count = info["raw_count"]
        unique_roster_ids = len(info["unique_ids"])
        ingested_count = ingested.get(div_name, 0)
        # Expected: use unique id count; optionally adjust (e.g., -1 if home team double counts)
        expected = max(0, unique_roster_ids + expected_adjustment)
        deficit = max(0, expected - ingested_count)
        surplus = max(0, ingested_count - expected)
        diagnostics.append(
            DivisionTeamDiagnostic(
                division_folder=folder,
                division_name=div_name,
                ingested_count=ingested_count,
                roster_file_count=roster_file_count,
                unique_roster_ids=unique_roster_ids,
                expected_count=expected,
                deficit=deficit,
                surplus=surplus,
                sample_files=info["roster_files"][:5],
            )
        )
    if write_json:
        try:
            out_dir = Path(base_dir) / "diagnostics"
            out_dir.mkdir(parents=True, exist_ok=True)
            with (out_dir / "team_count_comparison.json").open("w", encoding="utf-8") as f:
                json.dump([d.to_dict() for d in diagnostics], f, ensure_ascii=False, indent=2)
        except Exception:  # pragma: no cover - best effort
            pass
    return diagnostics
