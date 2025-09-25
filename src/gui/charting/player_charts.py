"""Player-specific chart builders (Milestone 7.3: LivePZ progression)."""
from __future__ import annotations

from typing import List, Tuple
import sqlite3

from .registry import register_chart_type
from .types import ChartRequest, ChartResult
from .backends import MatplotlibChartBackend
from gui.services.service_locator import services


def _fetch_player_livepz_history(player_id: str) -> List[Tuple[str, int]]:
    """Fetch (iso_date, live_pz) progression for player.

    Strategy: derive synthetic progression from roster LivePZ + match chronology if
    match-level player delta data is not yet present. For now we look up player's
    base live_pz and then create a flat series over their team's completed matches.
    This provides a time x-axis for the chart while future ingestion enhancements
    can replace with real per-match rating snapshots.
    """
    conn: sqlite3.Connection | None = services.try_get("sqlite_conn")
    if conn is None:
        return []
    try:
        row = conn.execute(
            "SELECT live_pz, team_id FROM player WHERE player_id=?", (player_id,)
        ).fetchone()
    except Exception:
        # Schema not present yet
        return []
    if not row:
        return []
    live_pz, team_id = row
    if live_pz is None:
        return []
    try:
        matches = conn.execute(
            "SELECT match_date FROM match WHERE (home_team_id=? OR away_team_id=?) AND home_score IS NOT NULL AND away_score IS NOT NULL ORDER BY match_date",
            (team_id, team_id),
        ).fetchall()
    except Exception:
        matches = []
    if not matches:
        # Single snapshot at synthetic date
        return [("2025-01-01", int(live_pz))]
    return [(m[0], int(live_pz)) for m in matches]


def _player_livepz_progression_builder(req: ChartRequest, backend: MatplotlibChartBackend) -> ChartResult:
    data = req.data
    if not isinstance(data, dict):
        raise TypeError("Player progression chart expects dict with 'player_id'")
    player_id = data.get("player_id")
    if not player_id:
        raise ValueError("Missing player_id")
    hist = _fetch_player_livepz_history(player_id)
    if not hist:
        # empty widget placeholder (single point)
        x = [0]
        y = [0]
        labels = None
    else:
        dates, values = zip(*hist)
        # Convert dates to sequential indices for now (matplotlib date formatting optional later)
        x = list(range(len(dates)))
        y = list(values)
        labels = None
    widget = backend.create_line_chart([y], labels=labels, title=req.options.get("title") if req.options else None, x_values=x)
    return ChartResult(widget=widget, meta={"points": len(y)})


register_chart_type(
    "player.livepz.progression", _player_livepz_progression_builder, "Player LivePZ progression line chart"
)
