"""IngestionCoordinator (Milestone 5.9.3).

Bridges scraped HTML assets into the SQLite database using repository
contracts / schema. For now this is a *minimal* ingestion pass that:

1. Runs DataAuditService to discover divisions and team roster files.
2. Derives division + team entities from filenames (no deep HTML parsing yet).
3. Performs idempotent upserts into divisions, clubs (placeholder), teams,
   and players (players are not yet parsed, placeholder only).
4. Emits an event via EventBus (if available) signaling data refresh.

Future milestones will:
- Parse actual roster HTML for player lists & attributes.
- Parse ranking table HTML for standings & match schedule.
- Compute hashes and skip unchanged ingestion (5.9.4).
- Provide transactional ingest and error channel (5.9.12, 5.9.13).
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
import sqlite3
from typing import Optional, Iterable

from .data_audit import DataAuditService
from .event_bus import EventBus, Event  # type: ignore

__all__ = ["IngestionCoordinator", "IngestionSummary"]


@dataclass
class IngestionSummary:
    divisions_ingested: int
    teams_ingested: int
    players_ingested: int
    skipped: int = 0


class IngestionCoordinator:
    """Coordinates ingestion of scraped assets into SQLite.

    Parameters
    ----------
    base_dir: str
        Directory containing scraped HTML assets.
    conn: sqlite3.Connection
        Database connection (repositories may share this).
    event_bus: Optional[EventBus]
        Event bus for emitting post-ingest notifications.
    """

    def __init__(
        self, base_dir: str, conn: sqlite3.Connection, event_bus: Optional[EventBus] = None
    ):
        self.base_dir = Path(base_dir)
        self.conn = conn
        self.event_bus = event_bus

    # Public ------------------------------------------------------
    def run(self) -> IngestionSummary:
        audit = DataAuditService(str(self.base_dir)).run()
        divisions_ingested = 0
        teams_ingested = 0
        players_ingested = 0

        with self.conn:  # single transaction for now (not per-division yet)
            # Upsert divisions
            for d in audit.divisions:
                self._upsert_division(d.division)
                divisions_ingested += 1
                # Teams derived from roster filenames
                for team_name, info in d.team_rosters.items():  # noqa: B007
                    team_id = self._derive_team_id(team_name)
                    # Placeholder: assign a synthetic club id for grouping
                    club_id = self._derive_club_id(team_name)
                    self._ensure_club(club_id)
                    self._upsert_team(team_id, team_name, d.division, club_id)
                    teams_ingested += 1
                    # Placeholder players (none parsed yet) -> skip

        summary = IngestionSummary(
            divisions_ingested=divisions_ingested,
            teams_ingested=teams_ingested,
            players_ingested=players_ingested,
            skipped=0,
        )
        if self.event_bus is not None:
            try:
                self.event_bus.publish(Event("DATA_REFRESHED", payload={"summary": summary}))
            except Exception:  # pragma: no cover - non-fatal
                pass
        return summary

    # Internal helpers --------------------------------------------
    def _upsert_division(self, division_id: str):
        self.conn.execute(
            "INSERT OR IGNORE INTO divisions(id, name) VALUES(?, ?)",
            (division_id, division_id.replace("_", " ")),  # naive name until real parsing
        )

    def _ensure_club(self, club_id: str):
        self.conn.execute(
            "INSERT OR IGNORE INTO clubs(id, name) VALUES(?, ?)",
            (club_id, club_id.replace("_", " ")),  # placeholder name
        )

    def _upsert_team(self, team_id: str, name: str, division_id: str, club_id: str | None):
        self.conn.execute(
            "INSERT OR REPLACE INTO teams(id, name, division_id, club_id) VALUES(?,?,?,?)",
            (team_id, name, division_id, club_id),
        )

    @staticmethod
    def _derive_team_id(team_name: str) -> str:
        return team_name.lower().replace(" ", "-")

    @staticmethod
    def _derive_club_id(team_name: str) -> str:
        # Heuristic: use first token as club grouping; refine later when real parsing is implemented
        return team_name.split()[0].lower()
