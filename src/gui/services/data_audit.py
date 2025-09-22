"""DataAuditService (Milestone 5.9.0)

Scans the scraped data directory to build an overview of available HTML assets
(roster pages, ranking tables) and correlates them superficially to expected
schema entities for later ingestion.

This does not parse HTML; it only inspects filenames and basic size / hash to
support change detection planning and coverage reporting.
"""

from __future__ import annotations
from dataclasses import dataclass, asdict
from pathlib import Path
from typing import Dict, List, Optional
import hashlib

__all__ = [
    "AuditFileInfo",
    "DivisionAudit",
    "DataAuditResult",
    "DataAuditService",
]


@dataclass
class AuditFileInfo:
    path: str
    size: int
    sha1: str


def _sha1(path: Path) -> str:
    h = hashlib.sha1()
    try:
        with path.open("rb") as f:
            while True:
                chunk = f.read(8192)
                if not chunk:
                    break
                h.update(chunk)
    except Exception:
        return ""
    return h.hexdigest()


@dataclass
class DivisionAudit:
    division: str
    ranking_table: Optional[AuditFileInfo]
    team_rosters: Dict[str, AuditFileInfo]  # key: team name (derived from filename)

    def to_dict(self):  # pragma: no cover - simple helper
        return {
            "division": self.division,
            "ranking_table": asdict(self.ranking_table) if self.ranking_table else None,
            "team_rosters": {k: asdict(v) for k, v in self.team_rosters.items()},
        }


@dataclass
class DataAuditResult:
    divisions: List[DivisionAudit]
    total_ranking_tables: int
    total_team_rosters: int

    def to_dict(self):  # pragma: no cover
        return {
            "divisions": [d.to_dict() for d in self.divisions],
            "total_ranking_tables": self.total_ranking_tables,
            "total_team_rosters": self.total_team_rosters,
        }


class DataAuditService:
    RANKING_PREFIX = "ranking_table_"
    TEAM_PREFIX = "team_roster_"

    def __init__(self, base_dir: str):
        self.base_dir = Path(base_dir)

    def run(self) -> DataAuditResult:
        divisions: Dict[str, DivisionAudit] = {}
        for root, dirs, files in self._walk():  # noqa: B007
            p = Path(root)
            for fname in files:
                if not fname.endswith(".html"):
                    continue
                if fname.startswith(self.RANKING_PREFIX):
                    # Backward-compatible removal of prefix/suffix (avoid str.removeprefix for <3.9)
                    base = fname
                    if base.startswith(self.RANKING_PREFIX):
                        base = base[len(self.RANKING_PREFIX) :]
                    if base.endswith(".html"):
                        base = base[:-5]
                    division = base
                    info = self._file_info(p / fname)
                    audit = divisions.setdefault(
                        division,
                        DivisionAudit(division=division, ranking_table=None, team_rosters={}),
                    )
                    audit.ranking_table = info
                elif fname.startswith(self.TEAM_PREFIX):
                    # Format (observed): team_roster_<division>_<Team_Name_...>_<id>.html
                    base = fname
                    if base.endswith(".html"):
                        base = base[:-5]
                    if base.startswith(self.TEAM_PREFIX):
                        base = base[len(self.TEAM_PREFIX) :]
                    stem = base
                    tokens = stem.split("_")
                    if len(tokens) < 3:  # need at least division + name + id
                        continue
                    team_id = tokens[-1]
                    # Reconstruct division by matching longest prefix that appears as a ranking_table_<division>.html in same dir (if present)
                    ranking_candidates = set()
                    for dn in files:
                        if not dn.startswith(self.RANKING_PREFIX):
                            continue
                        rbase = dn
                        if rbase.startswith(self.RANKING_PREFIX):
                            rbase = rbase[len(self.RANKING_PREFIX) :]
                        if rbase.endswith(".html"):
                            rbase = rbase[:-5]
                        ranking_candidates.add(rbase)
                    division = None
                    for i in range(
                        len(tokens) - 2, 0, -1
                    ):  # leave at least one token for team name + id
                        candidate = "_".join(tokens[:i])
                        if candidate in ranking_candidates:
                            division = candidate
                            team_name_tokens = tokens[i:-1]
                            break
                    if division is None:
                        # Fallback: first token as division
                        division = tokens[0]
                        team_name_tokens = tokens[1:-1]
                    team_name = " ".join(t.replace("-", " ") for t in team_name_tokens) or stem
                    info = self._file_info(p / fname)
                    audit = divisions.setdefault(
                        division,
                        DivisionAudit(division=division, ranking_table=None, team_rosters={}),
                    )
                    audit.team_rosters[team_name] = info
        # Aggregate stats
        ranking_count = sum(1 for d in divisions.values() if d.ranking_table)
        roster_count = sum(len(d.team_rosters) for d in divisions.values())
        return DataAuditResult(
            divisions=sorted(divisions.values(), key=lambda d: d.division),
            total_ranking_tables=ranking_count,
            total_team_rosters=roster_count,
        )

    # Internal ------------------------------------------------------
    def _walk(self):  # pragma: no cover - simple passthrough
        return [(str(p), dirs, files) for p, dirs, files in self._os_walk(self.base_dir)]

    def _os_walk(self, base: Path):  # separated for test override
        import os

        return os.walk(base)

    def _file_info(self, path: Path) -> AuditFileInfo:
        try:
            size = path.stat().st_size
        except Exception:
            size = 0
        return AuditFileInfo(path=str(path), size=size, sha1=_sha1(path))
