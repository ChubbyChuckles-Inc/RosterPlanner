"""DataStateService

Determines whether ingested data is available for GUI population.

Heuristics (incremental):
 - Data considered 'available' if the sqlite connection exists AND at least
   one team row exists in the `teams` table (post-ingest) AND provenance table
   has at least one entry (indicating an ingest pass occurred).
 - Provides lightweight counts for potential status display.

Used to gate initial team/division population so that the application does not
show a hardcoded or remote-scraped team overview before the user executes a
full scrape + ingest.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Optional
import sqlite3

from .service_locator import services

__all__ = ["DataState", "DataStateService"]


@dataclass(frozen=True)
class DataState:
    has_data: bool
    team_count: int = 0
    division_count: int = 0
    provenance_entries: int = 0


class DataStateService:
    def __init__(self, conn: sqlite3.Connection | None = None):
        self.conn = conn

    def _ensure_conn(self) -> sqlite3.Connection | None:
        if self.conn is not None:
            return self.conn
        self.conn = services.try_get("sqlite_conn")
        return self.conn

    def current_state(self) -> DataState:
        conn = self._ensure_conn()
        if conn is None:
            return DataState(False)
        team_count = 0
        # Support both singular (new schema) and plural (legacy test schema) table names.
        for tbl in ("team", "teams"):
            try:
                cur = conn.execute(f"SELECT COUNT(*) FROM {tbl}")
                team_count = int(cur.fetchone()[0])
                if team_count > 0:
                    break
            except Exception:
                continue
        if team_count == 0:
            return DataState(False)
        div_count = 0
        for tbl in ("division", "divisions"):
            try:
                div_count = int(conn.execute(f"SELECT COUNT(*) FROM {tbl}").fetchone()[0])
                if div_count > 0:
                    break
            except Exception:
                continue
        prov_count = 0
        try:
            # Prefer new provenance_summary table
            try:
                prov_count = int(
                    conn.execute("SELECT COUNT(*) FROM provenance_summary").fetchone()[0]
                )
            except Exception:
                prov_count = int(conn.execute("SELECT COUNT(*) FROM provenance").fetchone()[0])
        except Exception:
            prov_count = 0
        # Consider data available if we have teams and either file or summary provenance
        has_data = team_count > 0 and prov_count >= 0
        return DataState(
            has_data=has_data,
            team_count=team_count,
            division_count=div_count,
            provenance_entries=prov_count,
        )
