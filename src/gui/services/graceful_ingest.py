"""Graceful ingest helpers.

Expose a small, testable API that lets the GUI surface available data
even when an ingest ran partially (some divisions succeeded, some failed).

This module is intentionally small and DB-schema tolerant: it will work
with either the singular schema (`division`, `team`, `player`) or the
legacy plural schema (`divisions`, `teams`, `players`).
"""

from __future__ import annotations

from typing import Dict
import sqlite3


class GracefulIngestService:
    """Service to summarize available data after a partial ingest.

    The service returns a mapping of division name -> counts (teams, players).
    It is defensive: if expected tables are missing it will attempt reasonable
    fallbacks and always return a stable dictionary (possibly empty).
    """

    @staticmethod
    def _table_names(conn: sqlite3.Connection) -> set[str]:
        cur = conn.execute("SELECT name FROM sqlite_master WHERE type='table'")
        return {r[0] for r in cur.fetchall()}

    @classmethod
    def summarize_available(cls, conn: sqlite3.Connection) -> Dict[str, Dict[str, int]]:
        """Return available data summary per division.

        Args:
            conn: sqlite3 connection to the application DB (may be :memory: in tests).

        Returns:
            A mapping { division_name: { 'teams': int, 'players': int } }
        """
        try:
            tables = cls._table_names(conn)
            singular = "division" in tables
            div_table = "division" if singular else "divisions"
            team_table = "team" if singular else "teams"
            player_table = "player" if singular else "players"

            result: Dict[str, Dict[str, int]] = {}

            # If we have a division table, iterate it and count linked teams/players.
            if div_table in tables:
                # Support both column naming conventions (division_id vs id)
                id_col = "division_id" if singular else "id"
                name_col = "name"
                cur = conn.execute(f"SELECT {id_col}, {name_col} FROM {div_table}")
                for div_id, div_name in cur.fetchall():
                    # teams count
                    team_count = 0
                    player_count = 0
                    try:
                        team_count = int(
                            conn.execute(
                                f"SELECT COUNT(*) FROM {team_table} WHERE division_id=?",
                                (div_id,),
                            ).fetchone()[0]
                        )
                    except Exception:
                        # best-effort fallback: try to match textual division name
                        try:
                            team_count = int(
                                conn.execute(
                                    f"SELECT COUNT(*) FROM {team_table} WHERE name LIKE ?",
                                    (f"%{div_name}%",),
                                ).fetchone()[0]
                            )
                        except Exception:
                            team_count = 0

                    try:
                        player_count = int(
                            conn.execute(
                                f"SELECT COUNT(*) FROM {player_table} WHERE team_id IN (SELECT team_id FROM {team_table} WHERE division_id=?)",
                                (div_id,),
                            ).fetchone()[0]
                        )
                    except Exception:
                        player_count = 0

                    result[str(div_name)] = {"teams": team_count, "players": player_count}
                return result

            # No division table: try to derive divisions from team rows (division_id values)
            if team_table in tables:
                cur = conn.execute(f"SELECT DISTINCT division_id FROM {team_table}")
                for (div_id,) in cur.fetchall():
                    div_name = str(div_id)
                    team_count = int(
                        conn.execute(
                            f"SELECT COUNT(*) FROM {team_table} WHERE division_id=?", (div_id,)
                        ).fetchone()[0]
                    )
                    try:
                        player_count = int(
                            conn.execute(
                                f"SELECT COUNT(*) FROM {player_table} WHERE team_id IN (SELECT team_id FROM {team_table} WHERE division_id=?)",
                                (div_id,),
                            ).fetchone()[0]
                        )
                    except Exception:
                        player_count = 0
                    result[div_name] = {"teams": team_count, "players": player_count}

            return result
        except Exception:
            return {}
