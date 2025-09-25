"""Match-focused charts (Milestone 7.6: match volume timeline & cumulative win %).

The chart shows two normalized series over completed matches for a team:
    1. Cumulative matches played (normalized 0..1)
    2. Cumulative win percentage (0..1)

Reasons for normalization: Keeps both series on comparable scale without
adding secondary axis complexity in the current backend abstraction.
Metadata returned includes the raw counts so consumers can present exact
figures elsewhere (tooltip, side panel, etc.).

Graceful degradation: If schema/tables are missing or no matches are found,
returns an empty placeholder chart with status 'empty'.
"""

from __future__ import annotations

from typing import List, Tuple
import logging

from .registry import register_chart_type
from .types import ChartRequest, ChartResult
from .backends import MatplotlibChartBackend
from gui.services.service_locator import services

log = logging.getLogger(__name__)


def _fetch_team_completed_matches(team_id: int) -> List[Tuple[str, int, int]]:
    """Return list of (match_date, team_score, opp_score) for completed matches.

    Defensive: returns empty list if tables/columns missing.
    """
    conn = services.try_get("sqlite_conn")  # type: ignore[attr-defined]
    if conn is None:
        return []
    try:
        rows = conn.execute(
            "SELECT match_date, home_team_id, away_team_id, home_score, away_score "
            "FROM match WHERE (home_team_id=? OR away_team_id=?) AND home_score IS NOT NULL AND away_score IS NOT NULL "
            "ORDER BY match_date ASC, match_id ASC",
            (team_id, team_id),
        ).fetchall()
    except Exception as e:  # noqa: BLE001
        log.debug("match table missing or query failed: %s", e)
        return []
    result: List[Tuple[str, int, int]] = []
    for match_date, home_tid, away_tid, hs, as_ in rows:
        try:
            if home_tid == team_id:
                team_score, opp_score = int(hs), int(as_)
            else:
                team_score, opp_score = int(as_), int(hs)
            result.append((str(match_date), team_score, opp_score))
        except Exception:  # pragma: no cover - skip malformed row
            continue
    return result


def _match_volume_winpct_builder(
    req: ChartRequest, backend: MatplotlibChartBackend
) -> ChartResult:
    if not isinstance(req.data, dict):
        raise TypeError("match volume timeline expects dict data with 'team_id'")
    try:
        team_id = int(req.data.get("team_id"))  # type: ignore[arg-type]
    except Exception:  # noqa: BLE001
        raise ValueError("team_id parameter is required and must be int-like")

    matches = _fetch_team_completed_matches(team_id)
    if not matches:
        widget = backend.create_line_chart([], labels=None, title=req.options.get("title") if req.options else "Match Volume & Win %")
        return ChartResult(widget=widget, meta={"status": "empty"})

    cumulative_matches: List[float] = []
    cumulative_win_pct: List[float] = []
    wins = 0
    for idx, (_date, team_score, opp_score) in enumerate(matches, start=1):
        if team_score > opp_score:
            wins += 1
        cumulative_matches.append(idx)  # raw count for normalization later
        cumulative_win_pct.append(wins / idx)

    total_matches = len(matches)
    norm_matches = [c / total_matches for c in cumulative_matches]
    series = [norm_matches, cumulative_win_pct]
    labels = ["Cumulative Matches (norm)", "Cumulative Win %"]
    widget = backend.create_line_chart(
        series,
        labels=labels,
        title=req.options.get("title") if req.options else "Match Volume & Win %",
        x_values=list(range(1, total_matches + 1)),
    )
    return ChartResult(
        widget=widget,
        meta={
            "status": "ok",
            "team_id": team_id,
            "matches": total_matches,
            "wins": wins,
            "win_pct_final": wins / total_matches if total_matches else 0.0,
        },
    )


register_chart_type(
    "team.match_volume_winpct",
    _match_volume_winpct_builder,
    "Team match volume timeline & cumulative win % (normalized)",
)
