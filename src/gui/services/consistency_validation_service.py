"""ConsistencyValidationService (Milestone 5.9.20)

Performs lightweight post-ingest data consistency checks on the SQLite
schema used by the application. The intent is to surface *warnings* and
*errors* early so that upstream parser/ingestion issues are caught before
they propagate into GUI logic.

Scope (initial iteration):
 - Orphan teams (team.division_id not found in division)
 - Orphan players (player.team_id not found in team)
 - Orphan matches (match.division_id missing OR home/away team missing)
 - Basic aggregate counts (divisions, teams, players, matches)

Future extensions may include cross-count validations (e.g. each team
has at least one player) or logical constraints (no duplicate match
dates between same opponents, etc.).

Design Notes:
 - Non-invasive: does not mutate data, only reads.
 - Returns a dataclass result object for easy serialization / logging.
 - Integrates with IngestionCoordinator (optional) to run automatically
   after a successful ingest, registering the result in the service
   locator under key ``consistency_result`` for retrieval by GUI panels.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Dict, List, Optional
import sqlite3

from .service_locator import services

__all__ = ["ConsistencyValidationService", "ConsistencyValidationResult"]


@dataclass
class ConsistencyValidationResult:
    """Container for validation findings.

    Attributes
    ----------
    errors: list[str]
        Hard failures indicating broken foreign key style relationships.
    warnings: list[str]
        Non-fatal issues (currently unused; placeholder for future rules).
    stats: dict[str, int]
        Aggregate entity counts (divisions, teams, players, matches).
    """

    errors: List[str] = field(default_factory=list)
    warnings: List[str] = field(default_factory=list)
    stats: Dict[str, int] = field(default_factory=dict)

    def is_clean(self) -> bool:
        return not self.errors


class ConsistencyValidationService:
    """Runs post-ingest consistency checks.

    The service attempts to adapt to both the *singular* schema
    (division/team/player/match) and the legacy *plural* fallback
    (divisions/teams/players/matches). For plural mode it silently skips
    validations for tables not present.
    """

    def __init__(self, conn: sqlite3.Connection):
        self.conn = conn

    def validate(self) -> ConsistencyValidationResult:
        res = ConsistencyValidationResult()
        cur = self.conn.execute("SELECT name FROM sqlite_master WHERE type='table'")
        tables = {r[0] for r in cur.fetchall()}

        # Table name resolution
        tbl_div = (
            "division" if "division" in tables else ("divisions" if "divisions" in tables else None)
        )
        tbl_team = "team" if "team" in tables else ("teams" if "teams" in tables else None)
        tbl_player = (
            "player" if "player" in tables else ("players" if "players" in tables else None)
        )
        tbl_match = "match" if "match" in tables else ("matches" if "matches" in tables else None)

        # Basic counts
        try:
            if tbl_div:
                res.stats["divisions"] = self._scalar(f"SELECT COUNT(*) FROM {tbl_div}")
            if tbl_team:
                res.stats["teams"] = self._scalar(f"SELECT COUNT(*) FROM {tbl_team}")
            if tbl_player:
                res.stats["players"] = self._scalar(f"SELECT COUNT(*) FROM {tbl_player}")
            if tbl_match:
                res.stats["matches"] = self._scalar(f"SELECT COUNT(*) FROM {tbl_match}")
        except Exception:
            pass

        # Orphan checks (only if requisite tables available)
        try:
            if tbl_team and tbl_div and "division_id" in self._columns(tbl_team):
                rows = self.conn.execute(
                    f"SELECT t.rowid FROM {tbl_team} t LEFT JOIN {tbl_div} d ON t.division_id=d.division_id WHERE d.division_id IS NULL"
                ).fetchall()
                if rows:
                    res.errors.append(f"Orphan teams referencing missing division: {len(rows)}")
        except Exception:
            pass

        try:
            if tbl_player and tbl_team and "team_id" in self._columns(tbl_player):
                rows = self.conn.execute(
                    f"SELECT p.rowid FROM {tbl_player} p LEFT JOIN {tbl_team} t ON p.team_id=t.team_id WHERE t.team_id IS NULL"
                ).fetchall()
                if rows:
                    res.errors.append(f"Orphan players referencing missing team: {len(rows)}")
        except Exception:
            pass

        try:
            if tbl_match and tbl_div and "division_id" in self._columns(tbl_match):
                rows = self.conn.execute(
                    f"SELECT m.rowid FROM {tbl_match} m LEFT JOIN {tbl_div} d ON m.division_id=d.division_id WHERE d.division_id IS NULL"
                ).fetchall()
                if rows:
                    res.errors.append(f"Orphan matches referencing missing division: {len(rows)}")
        except Exception:
            pass

        try:
            if (
                tbl_match
                and tbl_team
                and {"home_team_id", "away_team_id"}.issubset(self._columns(tbl_match))
            ):
                rows = self.conn.execute(
                    f"SELECT m.rowid FROM {tbl_match} m LEFT JOIN {tbl_team} th ON m.home_team_id=th.team_id LEFT JOIN {tbl_team} ta ON m.away_team_id=ta.team_id WHERE th.team_id IS NULL OR ta.team_id IS NULL"
                ).fetchall()
                if rows:
                    res.errors.append(f"Orphan matches referencing missing team(s): {len(rows)}")
        except Exception:
            pass

        return res

    # Helpers ---------------------------------------------------
    def _scalar(self, sql: str) -> int:
        try:
            return int(self.conn.execute(sql).fetchone()[0])
        except Exception:
            return 0

    def _columns(self, table: str) -> set[str]:
        try:
            cur = self.conn.execute(f"PRAGMA table_info({table})")
            return {r[1] for r in cur.fetchall()}
        except Exception:
            return set()

    # Convenience static API -----------------------------------
    @staticmethod
    def run_and_register(conn: sqlite3.Connection) -> ConsistencyValidationResult:
        """Run validation and register result in service locator.

        Returns the result for immediate consumption.
        """
        svc = ConsistencyValidationService(conn)
        result = svc.validate()
        try:
            services.register("consistency_result", result, allow_override=True)
        except Exception:
            pass
        return result
