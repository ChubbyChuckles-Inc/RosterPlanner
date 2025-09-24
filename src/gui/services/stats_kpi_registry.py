"""KPI Registry (Milestone 6.1.1)

Provides declarative registration of statistics KPIs with metadata and a
uniform compute interface. Integrates with `StatsService` for underlying
calculations. Designed to be easily extended without modifying consumer
code (open/closed principle).

KPI Metadata Fields:
 - id: stable string identifier
 - label: human-friendly short name
 - description: longer explanation (tooltips / docs)
 - category: grouping (e.g., "Team", "Player")
 - units: optional units string (e.g., "%", "points")
 - compute: callable returning a value given a StatsService and target id
 - value_type: semantic hint ("float", "mapping", etc.)

The registry does not persist results or cache; callers may wrap with
memoization if needed (Milestone 6.7 will address caching/invalidation).
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Callable, Dict, Iterable, List, Optional, Protocol, Any

from .stats_service import StatsService

__all__ = ["KPI", "KPIRegistry", "global_kpi_registry", "register_default_kpis"]


class KPIComputeFn(Protocol):
    def __call__(self, svc: StatsService, target_id: str) -> Any:  # pragma: no cover - protocol
        ...


@dataclass(frozen=True)
class KPI:
    id: str
    label: str
    description: str
    category: str
    compute: KPIComputeFn
    value_type: str = "float"
    units: str | None = None
    # Future: dependencies, version, deprecation flag


@dataclass
class KPIRegistry:
    _kpis: Dict[str, KPI] = field(default_factory=dict)

    def register(self, kpi: KPI, *, overwrite: bool = False) -> None:
        if (not overwrite) and kpi.id in self._kpis:
            raise ValueError(f"KPI already registered: {kpi.id}")
        self._kpis[kpi.id] = kpi

    def list_ids(self) -> List[str]:
        return sorted(self._kpis.keys())

    def get(self, kpi_id: str) -> KPI | None:
        return self._kpis.get(kpi_id)

    def compute(self, kpi_id: str, svc: StatsService, target_id: str) -> Any:
        kpi = self.get(kpi_id)
        if kpi is None:
            raise KeyError(kpi_id)
        return kpi.compute(svc, target_id)


global_kpi_registry = KPIRegistry()


def register_default_kpis(registry: KPIRegistry | None = None) -> KPIRegistry:
    """Idempotently register baseline KPIs if not present.

    Returns the registry for chaining.
    """
    reg = registry or global_kpi_registry
    # Helper guards to avoid duplicate registration in repeated test runs.
    if "team.win_pct" not in reg._kpis:
        reg.register(
            KPI(
                id="team.win_pct",
                label="Win %",
                description="Completed match win percentage (wins + 0.5*draws) / completed matches",
                category="Team",
                units="%",
                value_type="float",
                compute=lambda svc, tid: (
                    None
                    if (svc.team_win_percentage(tid) is None)
                    else round(svc.team_win_percentage(tid) * 100.0, 2)
                ),
            )
        )
    if "team.avg_top4_lpz" not in reg._kpis:
        reg.register(
            KPI(
                id="team.avg_top4_lpz",
                label="Avg Top4 LivePZ",
                description="Average LivePZ rating of top 4 players (by LivePZ)",
                category="Team",
                units="LivePZ",
                value_type="float",
                compute=lambda svc, tid: svc.average_top_live_pz(tid, top_n=4),
            )
        )
    if "team.participation_uniform" not in reg._kpis:
        reg.register(
            KPI(
                id="team.participation_uniform",
                label="Participation (Uniform)",
                description="Uniform participation heuristic (placeholder until per-match lineup ingested)",
                category="Team",
                value_type="mapping",
                compute=lambda svc, tid: svc.player_participation_rate(tid),
            )
        )
    return reg
