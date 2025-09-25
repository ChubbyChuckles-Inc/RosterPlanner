"""Team-focused chart builders (availability heatmap, etc.).

Implements Milestone 7.4 (Team availability heatmap) in a provisional manner.
Because the dedicated availability schema (Milestone 8) is not yet defined,
we derive a placeholder 'availability score' from historical match participation
heuristics if match data is present. If not, we generate an empty matrix so the
chart still renders without errors.

Heuristic (temporary):
    value = 1.0 if player participated in a match on that date, else 0.0.

Future extension (once availability schema exists):
    - Replace _fetch_team_availability_matrix implementation to query the
      availability table (probability, confirmed, tentative, absent, unknown).
    - Potential color scale adjustments (multi-category discrete mapping).
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable, List, Sequence, Tuple
import logging

from .registry import register_chart_type, chart_registry
from .types import ChartRequest, ChartResult

log = logging.getLogger(__name__)


@dataclass
class _TeamAvailabilityParams:
    team_id: int
    # Optional window (inclusive) of dates as ISO strings (YYYY-MM-DD) to restrict heatmap
    start_date: str | None = None
    end_date: str | None = None


def _fetch_team_player_list(team_id: int) -> List[Tuple[int, str]]:
    """Return list of (player_id, display_name) for the given team.

    Defensive: if tables are missing returns empty list.
    """
    try:
        import sqlite3
        from src.config import get_database_path  # type: ignore

        path = get_database_path()
        conn = sqlite3.connect(path)
        cur = conn.cursor()
        # This assumes a linking table team_player(team_id, player_id) and player(id, name)
        # which may not yet exist; we guard for that.
        try:
            cur.execute(
                "SELECT p.id, p.name FROM team_player tp JOIN player p ON p.id = tp.player_id WHERE tp.team_id = ? ORDER BY p.name",
                (team_id,),
            )
            rows = [(int(r[0]), str(r[1])) for r in cur.fetchall()]
        except Exception as e:  # broad: schema not ready
            log.debug("team_player/player tables missing or query failed: %s", e)
            rows = []
        finally:
            conn.close()
        return rows
    except Exception as e:  # pragma: no cover - catastrophic path
        log.warning("Failed to fetch team player list: %s", e)
        return []


def _fetch_team_availability_matrix(
    team_id: int, start_date: str | None, end_date: str | None
) -> Tuple[List[str], List[str], List[List[float]]]:
    """Return (dates, player_names, matrix) for availability.

    Placeholder implementation using match participation if tables exist.
    Matrix rows correspond to players (order stable w.r.t fetched list), columns to dates.
    """
    players = _fetch_team_player_list(team_id)
    if not players:
        return [], [], []

    try:
        import sqlite3
        from src.config import get_database_path  # type: ignore
        path = get_database_path()
        conn = sqlite3.connect(path)
        cur = conn.cursor()

        # Collect distinct match dates for this team
        date_query = [
            "SELECT DISTINCT date FROM match WHERE (home_team_id = ? OR away_team_id = ?)",
        ]
        params: List[str | int] = [team_id, team_id]
        if start_date:
            date_query.append("AND date >= ?")
            params.append(start_date)
        if end_date:
            date_query.append("AND date <= ?")
            params.append(end_date)
        date_sql = " ".join(date_query) + " ORDER BY date"
        try:
            cur.execute(date_sql, tuple(params))
            dates = [r[0] for r in cur.fetchall()]
        except Exception as e:
            log.debug("match table/date column missing: %s", e)
            dates = []

        # Build quick lookup of (player_id, date) -> participation
        participation: set[tuple[int, str]] = set()
        if dates:
            try:
                cur.execute(
                    "SELECT player_id, date FROM match_participation WHERE team_id = ?",
                    (team_id,),
                )
                participation = {(int(r[0]), str(r[1])) for r in cur.fetchall()}
            except Exception as e:
                log.debug("match_participation table missing: %s", e)
        conn.close()
    except Exception as e:  # pragma: no cover - unexpected environment issue
        log.warning("Failed fetching availability matrix: %s", e)
        return [], [p[1] for p in players], []

    if not dates:
        return [], [p[1] for p in players], []

    matrix: List[List[float]] = []
    for pid, _name in players:
        row = [1.0 if (pid, d) in participation else 0.0 for d in dates]
        matrix.append(row)
    return dates, [p[1] for p in players], matrix


def _team_availability_heatmap_builder(req: ChartRequest, backend) -> ChartResult:
    params = req.data if isinstance(req.data, dict) else {}
    try:
        team_id = int(params.get("team_id"))  # type: ignore[arg-type]
    except Exception:  # noqa: BLE001
        raise ValueError("team_id parameter is required and must be int-like")
    start_date = params.get("start_date") if params else None
    end_date = params.get("end_date") if params else None

    dates, player_names, matrix = _fetch_team_availability_matrix(team_id, start_date, end_date)
    if not dates or not player_names or not matrix:
        # Provide a tiny empty placeholder widget (empty heatmap)
        widget = backend.create_heatmap(matrix=[], x_labels=[], y_labels=[], title="Team Availability (empty)")
        return ChartResult(widget=widget, meta={"status": "empty"})

    widget = backend.create_heatmap(
        matrix=matrix,
        x_labels=dates,
        y_labels=player_names,
        title="Team Availability",
        cmap="Blues",
    )
    return ChartResult(widget=widget, meta={"status": "ok", "players": len(player_names), "dates": len(dates)})


# Register chart type (provisional availability heatmap)
register_chart_type(
    "team_availability_heatmap",
    _team_availability_heatmap_builder,
    "Team availability heatmap (provisional, based on match participation)",
)
