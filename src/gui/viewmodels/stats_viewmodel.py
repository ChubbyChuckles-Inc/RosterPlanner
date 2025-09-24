"""Stats ViewModel (Milestone 6 UI integration)

Bridges statistics services (KPI registry, time-series builder, histogram) to the
Stats Dock view. Keeps GUI widgets decoupled from repository/DB concerns.

Design:
 - Pull-only model: explicit `load_for_team(team_id)` populates state.
 - Exposes lightweight serializable structures for easy testing.
 - Defers caching (Milestone 6.7) – current calls are direct.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Dict, List, Any, Optional

from gui.services.stats_service import StatsService
from gui.services.stats_kpi_registry import register_default_kpis, global_kpi_registry
from gui.services.stats_timeseries_service import TimeSeriesBuilder, TimeSeriesPoint
from gui.services.stats_histogram_service import HistogramService, HistogramResult


@dataclass
class KPIValue:
    id: str
    label: str
    value: Any
    units: str | None = None


@dataclass
class StatsState:
    team_id: str | None = None
    kpis: List[KPIValue] = field(default_factory=list)
    timeseries: List[TimeSeriesPoint] = field(default_factory=list)
    histogram: HistogramResult | None = None


class StatsViewModel:
    def __init__(self, stats_service: StatsService | None = None):
        self._svc = stats_service or StatsService()
        register_default_kpis()
        self._ts = TimeSeriesBuilder(self._svc.conn)
        self._hist = HistogramService(self._svc.conn)
        self.state = StatsState()

    # ------------------------------------------------------------------
    def load_for_team(self, team_id: str) -> StatsState:
        self.state = StatsState(team_id=team_id)
        # KPIs
        kpi_values: List[KPIValue] = []
        for kpi_id in global_kpi_registry.list_ids():
            kpi = global_kpi_registry.get(kpi_id)
            if not kpi:
                continue
            try:
                val = global_kpi_registry.compute(kpi_id, self._svc, team_id)
            except Exception:
                val = None
            kpi_values.append(
                KPIValue(id=kpi.id, label=kpi.label, value=val, units=getattr(kpi, "units", None))
            )
        self.state.kpis = kpi_values
        # Time-series
        try:
            self.state.timeseries = self._ts.build_team_match_timeseries(team_id)
        except Exception:
            self.state.timeseries = []
        # Histogram
        try:
            self.state.histogram = self._hist.build_team_live_pz_histogram(team_id)
        except Exception:
            self.state.histogram = None
        return self.state

    # Convenience accessors -----------------------------------------------------
    def kpi_dict(self) -> Dict[str, Any]:  # for tests / serialization
        return {k.id: k.value for k in self.state.kpis}

    def timeseries_rows(self) -> List[Dict[str, Any]]:
        return [p.__dict__ for p in self.state.timeseries]

    def histogram_counts(self) -> Dict[str, int] | None:
        return self.state.histogram.as_dict() if self.state.histogram else None


__all__ = ["StatsViewModel", "StatsState", "KPIValue"]
