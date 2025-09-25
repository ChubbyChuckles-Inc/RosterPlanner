"""Statistics Profiling Harness (Milestone 6.9)

Provides a programmatic way to benchmark core analytics services over a
synthetic dataset so future regressions (time or memory) can be detected.

Scope of measurements (per run):
 - KPI batch (team_win_percentage + average_top_live_pz for all teams)
 - Division strength index (compute_division) + rating history
 - Rolling form (TrendDetectionService) for all teams
 - Match outcome predictor for each scheduled match (top-N players)
 - Cache effectiveness (first vs second pass on division strength)

Outputs timing (wall clock perf_counter) per phase and peak memory usage
captured via ``tracemalloc``. Designed to be invoked inside a pytest
performance test but also usable ad-hoc (e.g. from a REPL) to inspect
profiling numbers.

The synthetic dataset deliberately aims for moderate size (hundreds of
matches) so the harness stays fast (<1-2s on typical dev hardware) while
still exercising loops with enough iterations to catch O(N^2) mistakes.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, Any, List, Tuple
import random
import time
import sqlite3
import tracemalloc

from .service_locator import services
from .stats_service import StatsService
from .division_strength_index_service import DivisionStrengthIndexService
from .trend_detection_service import TrendDetectionService
from src.services.match_outcome_predictor_service import MatchOutcomePredictorService
from .stats_cache_service import StatsCacheService

__all__ = [
    "StatsProfilingResult",
    "run_stats_profiling",
]


@dataclass(frozen=True)
class StatsProfilingResult:
    dataset: Dict[str, Any]
    durations: Dict[str, float]
    peak_memory_bytes: int
    cache_speedup_ratio: float | None


def _ensure_tables(conn: sqlite3.Connection) -> None:
    conn.executescript(
        """
        CREATE TABLE IF NOT EXISTS division(division_id TEXT PRIMARY KEY, name TEXT, level TEXT, category TEXT);
        CREATE TABLE IF NOT EXISTS team(team_id TEXT PRIMARY KEY, club_id TEXT, division_id TEXT, name TEXT);
        CREATE TABLE IF NOT EXISTS player(player_id TEXT PRIMARY KEY, team_id TEXT, full_name TEXT, live_pz INTEGER);
        CREATE TABLE IF NOT EXISTS match(match_id TEXT PRIMARY KEY, division_id TEXT, home_team_id TEXT, away_team_id TEXT, match_date TEXT, round INTEGER, home_score INTEGER, away_score INTEGER);
        """
    )


def _synthetic_dataset(
    conn: sqlite3.Connection,
    *,
    divisions: int = 1,
    teams_per_division: int = 12,
    players_per_team: int = 8,
    rounds: int = 1,
    seed: int = 42,
) -> Dict[str, Any]:
    """Populate an in-memory schema with synthetic data.

    A round-robin (single) schedule is generated for each division.
    Scores are pseudo-random with moderate variance ensuring a mix of
    wins and losses.
    """
    random.seed(seed)
    _ensure_tables(conn)
    division_ids: List[str] = []
    team_ids: List[str] = []
    match_ids: List[str] = []
    player_ids: List[str] = []

    for d in range(divisions):
        div_id = f"D{d+1}"
        division_ids.append(div_id)
        conn.execute(
            "INSERT INTO division(division_id, name, level, category) VALUES (?,?,?,?)",
            (div_id, f"Division {d+1}", "L1", "Adults"),
        )
        # Teams
        current_div_team_ids: List[str] = []
        for t in range(teams_per_division):
            tid = f"T{d+1}_{t+1}"
            current_div_team_ids.append(tid)
            team_ids.append(tid)
            conn.execute(
                "INSERT INTO team(team_id, club_id, division_id, name) VALUES (?,?,?,?)",
                (tid, f"C{t+1}", div_id, f"Team {d+1}-{t+1}"),
            )
            # Players
            base = 1550 + 50 * random.random()  # cluster near 1550-1600
            for p in range(players_per_team):
                pid = f"P{tid}_{p+1}"
                player_ids.append(pid)
                live_pz = int(base + random.gauss(0, 120))
                conn.execute(
                    "INSERT INTO player(player_id, team_id, full_name, live_pz) VALUES (?,?,?,?)",
                    (pid, tid, f"Player {tid}-{p+1}", live_pz),
                )
        # Matches: single round-robin (each unordered pair once)
        # Simple date sequence
        date_counter = 1
        for i in range(len(current_div_team_ids)):
            for j in range(i + 1, len(current_div_team_ids)):
                home = current_div_team_ids[i]
                away = current_div_team_ids[j]
                # Random but reproducible score around 9:6 style (table tennis team match) limited 0..10
                base_home = random.randint(5, 10)
                base_away = random.randint(5, 10)
                # Avoid draws by nudging if equal
                if base_home == base_away:
                    if random.random() < 0.5:
                        base_home += 1
                    else:
                        base_away += 1
                mid = f"M{div_id}_{home}_{away}"
                match_ids.append(mid)
                conn.execute(
                    "INSERT INTO match(match_id, division_id, home_team_id, away_team_id, match_date, round, home_score, away_score) VALUES (?,?,?,?,?,?,?,?)",
                    (
                        mid,
                        div_id,
                        home,
                        away,
                        f"2025-01-{date_counter:02d}",
                        1,
                        base_home,
                        base_away,
                    ),
                )
                date_counter += 1
    conn.commit()
    return {
        "divisions": len(division_ids),
        "teams": len(team_ids),
        "players": len(player_ids),
        "matches": len(match_ids),
    }


def run_stats_profiling(
    conn: sqlite3.Connection,
    *,
    dataset_config: Dict[str, Any] | None = None,
) -> StatsProfilingResult:
    """Execute profiling phases and return structured result.

    Parameters
    ----------
    conn : sqlite3.Connection
        Target in-memory (or temp) database connection.
    dataset_config : dict | None
        Optional overrides for synthetic dataset generation.
    """
    if services.try_get("sqlite_conn") is None:
        services.register("sqlite_conn", conn)

    # 1. Data generation --------------------------------------------------
    cfg = {
        "divisions": 1,
        "teams_per_division": 12,
        "players_per_team": 8,
        "rounds": 1,
        "seed": 42,
    }
    if dataset_config:
        cfg.update(dataset_config)
    dataset_meta = _synthetic_dataset(conn, **cfg)

    # Prepare service instances
    stats = StatsService(conn)
    dsi = DivisionStrengthIndexService()
    trend = TrendDetectionService()
    predictor = MatchOutcomePredictorService()
    cache = StatsCacheService()

    durations: Dict[str, float] = {}

    # 2. KPI batch --------------------------------------------------------
    t0 = time.perf_counter()
    # For every team compute two KPIs
    team_ids = [r[0] for r in conn.execute("SELECT team_id FROM team").fetchall()]
    for tid in team_ids:
        stats.team_win_percentage(tid)
        stats.average_top_live_pz(tid)
    durations["kpis"] = time.perf_counter() - t0

    # 3. Division strength + history -------------------------------------
    division_id = conn.execute("SELECT division_id FROM division LIMIT 1").fetchone()[0]
    t0 = time.perf_counter()
    dsi.compute_division(division_id)
    durations["division_strength"] = time.perf_counter() - t0
    t0 = time.perf_counter()
    dsi.compute_rating_history(division_id)
    durations["division_strength_history"] = time.perf_counter() - t0

    # 4. Rolling form (all teams) ----------------------------------------
    t0 = time.perf_counter()
    for tid in team_ids:
        trend.team_rolling_form(tid)
    durations["rolling_form"] = time.perf_counter() - t0

    # 5. Predictor over every match --------------------------------------
    t0 = time.perf_counter()
    # Build top roster lists once for efficiency
    # (We just query players and sort by live_pz)
    players_by_team: Dict[str, List[int]] = {}
    for row in conn.execute(
        "SELECT team_id, live_pz FROM player WHERE live_pz IS NOT NULL ORDER BY live_pz DESC"
    ):
        players_by_team.setdefault(row[0], []).append(int(row[1]))
    for row in conn.execute("SELECT home_team_id, away_team_id FROM match ORDER BY match_date"):
        home, away = row
        predictor.predict(players_by_team.get(home, [])[:4], players_by_team.get(away, [])[:4])
    durations["predictor"] = time.perf_counter() - t0

    # 6. Cache effectiveness (compute same division strength twice) ------
    def _compute():
        return dsi.compute_division(division_id)

    t0 = time.perf_counter()
    cache.get_or_compute("division.strength", {"division_id": division_id}, _compute)
    first = time.perf_counter() - t0
    t0 = time.perf_counter()
    cache.get_or_compute("division.strength", {"division_id": division_id}, _compute)
    second = time.perf_counter() - t0
    durations["cache_first"] = first
    durations["cache_second"] = second
    cache_speedup = first / second if second > 0 else None

    # 7. Memory profiling (peak) -----------------------------------------
    # We only want memory used during analytical passes; so start tracing right before
    # re-running a combined pass of representative operations.
    tracemalloc.start()
    # Run a mini composite workload
    dsi.compute_division(division_id)
    dsi.compute_rating_history(division_id)
    for tid in team_ids[: min(4, len(team_ids))]:
        trend.team_rolling_form(tid)
    for row in conn.execute(
        "SELECT home_team_id, away_team_id FROM match ORDER BY match_date LIMIT 10"
    ):
        home, away = row
        predictor.predict(players_by_team.get(home, [])[:4], players_by_team.get(away, [])[:4])
    current, peak = tracemalloc.get_traced_memory()
    tracemalloc.stop()

    return StatsProfilingResult(
        dataset={**cfg, **dataset_meta},
        durations=durations,
        peak_memory_bytes=peak,
        cache_speedup_ratio=cache_speedup,
    )
