"""Division-focused chart builders (Milestone 7.5: standings evolution).

Produces a line chart showing each team's position in the division standings
over time (per match date snapshot). Because a dedicated standings snapshot
table may not yet exist, we reconstruct positions incrementally from the
completed matches table if present.

Current heuristic / assumptions (provisional):
    - We consider only matches with non-null scores.
    - Win criterion: higher score => +1 win point; losses and draws add 0.
    - Position ordering: descending by win points, then by team name for a
      deterministic tie-break. Future enhancement can incorporate official
      tie-breaking rules (sets ratio, points, head-to-head, etc.).
    - Snapshots are taken after each distinct match_date. This approximates
      a "round" progression without needing full round scheduling metadata.

Graceful degradation:
    - If required tables (team, match) are missing the builder returns an
      empty chart placeholder (meta.status == 'empty').
"""

from __future__ import annotations

from typing import Dict, List, Tuple
import logging

from .registry import register_chart_type
from .types import ChartRequest, ChartResult
from .backends import MatplotlibChartBackend
from gui.services.service_locator import services

log = logging.getLogger(__name__)


def _fetch_division_teams(division_id: int) -> List[Tuple[int, str]]:
    conn = services.try_get("sqlite_conn")  # type: ignore[attr-defined]
    if conn is None:
        return []
    try:
        rows = conn.execute(
            "SELECT team_id, name FROM team WHERE division_id=? ORDER BY name", (division_id,)
        ).fetchall()
        return [(int(r[0]), str(r[1])) for r in rows]
    except Exception as e:  # noqa: BLE001
        log.debug("team table missing or query failed: %s", e)
        return []


def _fetch_division_matches(division_id: int):
    conn = services.try_get("sqlite_conn")
    if conn is None:
        return []
    try:
        rows = conn.execute(
            "SELECT match_date, home_team_id, away_team_id, home_score, away_score FROM match "
            "WHERE division_id=? AND home_score IS NOT NULL AND away_score IS NOT NULL "
            "ORDER BY match_date ASC, match_id ASC",
            (division_id,),
        ).fetchall()
        return rows
    except Exception as e:  # noqa: BLE001
        log.debug("match table missing or query failed: %s", e)
        return []


def _reconstruct_standings_evolution(division_id: int):
    teams = _fetch_division_teams(division_id)
    if not teams:
        return [], [], []
    team_ids = [tid for tid, _ in teams]
    team_name_map = {tid: name for tid, name in teams}
    matches = _fetch_division_matches(division_id)
    if not matches:
        return [], [t[1] for t in teams], []

    # Initialize win points
    points: Dict[int, int] = {tid: 0 for tid in team_ids}
    snapshots: List[str] = []  # labels (match_date snapshots)
    evolution: Dict[int, List[int]] = {tid: [] for tid in team_ids}

    current_date = None
    processed_this_date: List[Tuple] = []

    def take_snapshot(date_label: str):
        # Order teams by points desc then name
        ordered = sorted(team_ids, key=lambda t: (-points[t], team_name_map[t]))
        pos_map = {tid: idx + 1 for idx, tid in enumerate(ordered)}
        for tid in team_ids:
            evolution[tid].append(pos_map[tid])
        snapshots.append(date_label)

    for match_date, home_id, away_id, home_score, away_score in matches:
        if current_date is None:
            current_date = match_date
        if match_date != current_date:
            # end of previous date => snapshot
            take_snapshot(str(current_date))
            current_date = match_date
            processed_this_date.clear()
        # Update points for this match
        try:
            hs = int(home_score)
            as_ = int(away_score)
            if hs > as_:
                points[int(home_id)] += 1
            elif as_ > hs:
                points[int(away_id)] += 1
            # draws => no points (placeholder rule)
        except Exception:  # pragma: no cover - defensive
            pass
        processed_this_date.append((home_id, away_id))
    # Final snapshot
    if current_date is not None:
        take_snapshot(str(current_date))

    matrix = [evolution[tid] for tid in team_ids]
    return snapshots, [team_name_map[tid] for tid in team_ids], matrix


def _division_standings_evolution_builder(
    req: ChartRequest, backend: MatplotlibChartBackend
) -> ChartResult:
    if not isinstance(req.data, dict):
        raise TypeError("division standings evolution expects dict data with 'division_id'")
    try:
        division_id = int(req.data.get("division_id"))  # type: ignore[arg-type]
    except Exception:  # noqa: BLE001
        raise ValueError("division_id parameter is required and must be int-like")

    snapshots, team_names, matrix = _reconstruct_standings_evolution(division_id)
    if not snapshots or not matrix:
        # empty placeholder (line chart with 0 series)
        widget = backend.create_line_chart(
            [], labels=None, title=req.options.get("title") if req.options else None
        )
        return ChartResult(widget=widget, meta={"status": "empty"})

    # Each row in matrix is a team's positions list per snapshot
    widget = backend.create_line_chart(
        matrix,
        labels=team_names,
        title=req.options.get("title") if req.options else "Division Standings Evolution",
        x_values=list(range(1, len(snapshots) + 1)),
    )
    return ChartResult(
        widget=widget,
        meta={
            "status": "ok",
            "teams": len(team_names),
            "rounds": len(snapshots),
        },
    )


register_chart_type(
    "division.standings.evolution",
    _division_standings_evolution_builder,
    "Division standings evolution (positions over match-date snapshots)",
)
