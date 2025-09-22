"""Database Integrity Checks (Milestone 3.4 / 3.4.1)

Provides programmatic integrity verification routines:
 - Foreign key violations (PRAGMA foreign_key_check)
 - Uniqueness of team name per season (logical rule; schema currently enforces (division_id, name) but
   we also want to detect accidental duplicates across divisions for the same season if that becomes a data concern)

Returned structure is a list of dictionaries so callers (CLI, GUI, tests) can render or assert.

Future extensions (roadmap):
 - Player duplication heuristics
 - Orphaned matches
 - LivePZ value sanity ranges
"""

from __future__ import annotations

from dataclasses import dataclass, asdict
from typing import List, Dict, Any
import sqlite3


@dataclass
class IntegrityIssue:
    category: str
    message: str
    details: Dict[str, Any]

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


def _check_foreign_keys(conn: sqlite3.Connection) -> List[IntegrityIssue]:
    cur = conn.cursor()
    cur.execute("PRAGMA foreign_key_check")
    issues: List[IntegrityIssue] = []
    for table, rowid, parent, fkid in cur.fetchall():  # type: ignore
        issues.append(
            IntegrityIssue(
                category="foreign_key",
                message=f"Foreign key violation in table '{table}' referencing '{parent}'",
                details={"table": table, "rowid": rowid, "parent": parent, "fkid": fkid},
            )
        )
    return issues


def _check_team_uniqueness_per_season(conn: sqlite3.Connection) -> List[IntegrityIssue]:
    cur = conn.cursor()
    # We treat a duplicate if the same team name appears in more than one division for the same season.
    # (Business rule candidate; adjust as domain clarifies.)
    query = """
        SELECT t.name, d.season, COUNT(DISTINCT d.division_id) as div_count
        FROM team t
        JOIN division d ON d.division_id = t.division_id
        GROUP BY t.name, d.season
        HAVING div_count > 1
    """
    cur.execute(query)
    issues: List[IntegrityIssue] = []
    for name, season, div_count in cur.fetchall():
        issues.append(
            IntegrityIssue(
                category="team_name_duplicate",
                message=f"Team name '{name}' appears in {div_count} divisions for season {season}",
                details={"team_name": name, "season": season, "divisions": div_count},
            )
        )
    return issues


def run_integrity_checks(conn: sqlite3.Connection) -> List[Dict[str, Any]]:
    """Run all integrity checks and return list of issue dictionaries.

    Empty list indicates a clean database according to current rules.
    """
    issues: List[IntegrityIssue] = []
    issues.extend(_check_foreign_keys(conn))
    issues.extend(_check_team_uniqueness_per_season(conn))
    return [i.to_dict() for i in issues]


__all__ = ["run_integrity_checks", "IntegrityIssue"]
