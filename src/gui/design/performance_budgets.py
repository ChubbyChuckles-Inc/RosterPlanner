"""Component performance budget matrix (Milestone 0.16).

Defines baseline render/update performance targets for core component classes to
support early detection of regressions. Budgets are intentionally conservative
initial placeholders; they can be tuned as empirical measurements mature.

Purpose:
 - Provide a single source of truth for performance expectations.
 - Allow tests to assert that measured timings (microbenchmarks) remain below thresholds.
 - Create semantic grouping (render vs update vs animation frame costs).

Design Choices:
 - No runtime measurement logic here; enforcement test(s) provide numbers.
 - Keep units in milliseconds for readability.
 - Provide a helper `enforce_budget` to compare a dict of measurements vs budgets.
 - Avoid external deps; pure Python & dataclasses for Python 3.8 compatibility.

Future Extensions:
 - Integrate with timing decorator (Milestone P2) to auto-collect real measurements.
 - Add percentile tracking (P95/P99) once instrumentation is in place.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, List, Iterable, Tuple

__all__ = [
    "PerformanceBudget",
    "list_performance_budgets",
    "get_performance_budget",
    "enforce_budget",
]


@dataclass(frozen=True)
class PerformanceBudget:
    """Represents a performance threshold set for a component category.

    Attributes
    ----------
    name: str
        Identifier of the component grouping (e.g., 'NavigationTree').
    render_ms: float
        Target max (approx) cold render time per instance.
    update_ms: float
        Target max for typical incremental state update.
    frame_ms: float
        Target max cost for per-frame work (animation / periodic repaint); should
        usually be well below 16.6ms (60 FPS budget).
    notes: str
        Free-form rationale / context.
    """

    name: str
    render_ms: float
    update_ms: float
    frame_ms: float
    notes: str = ""


_REGISTRY: Dict[str, PerformanceBudget] = {}


def _register(b: PerformanceBudget) -> None:
    if b.name in _REGISTRY:
        raise ValueError(f"Duplicate performance budget name: {b.name}")
    _REGISTRY[b.name] = b


# Seed initial budgets (placeholder values; optimized later)
_register(
    PerformanceBudget(
        name="NavigationTree",
        render_ms=25.0,
        update_ms=6.0,
        frame_ms=1.5,
        notes="Tree model population & first paint; incremental expand/collapse minimal",
    )
)
_register(
    PerformanceBudget(
        name="DetailView-Team",
        render_ms=40.0,
        update_ms=10.0,
        frame_ms=2.0,
        notes="Roster + matches table initial layout; update = new match appended",
    )
)
_register(
    PerformanceBudget(
        name="StatsPanel",
        render_ms=30.0,
        update_ms=8.0,
        frame_ms=2.0,
        notes="Aggregated KPI list + small charts placeholder",
    )
)
_register(
    PerformanceBudget(
        name="PlannerScenarioEditor",
        render_ms=55.0,
        update_ms=15.0,
        frame_ms=3.0,
        notes="Scenario form + lineup list; heavier due to validation wiring",
    )
)
_register(
    PerformanceBudget(
        name="ChartCanvas",
        render_ms=35.0,
        update_ms=12.0,
        frame_ms=4.0,
        notes="Chart initialization + first data bind; update = new data points",
    )
)


def list_performance_budgets() -> List[PerformanceBudget]:
    return sorted(_REGISTRY.values(), key=lambda b: b.name)


def get_performance_budget(name: str) -> PerformanceBudget:
    budget = _REGISTRY.get(name)
    if budget is None:
        raise KeyError(f"Unknown performance budget: {name}")
    return budget


def enforce_budget(measurements: Dict[str, Dict[str, float]]) -> List[str]:
    """Compare measurement dict against registered budgets.

    Parameters
    ----------
    measurements: dict
        Mapping of component name -> { 'render_ms': x, 'update_ms': y, 'frame_ms': z }

    Returns
    -------
    list[str]
        List of violation messages (empty if all within budget).
    """
    violations: List[str] = []
    for name, m in measurements.items():
        try:
            b = get_performance_budget(name)
        except KeyError:
            violations.append(f"[unknown-component] {name}")
            continue
        for field in ("render_ms", "update_ms", "frame_ms"):
            if field not in m:
                violations.append(f"[missing-metric] {name}.{field}")
                continue
            value = m[field]
            budget_value = getattr(b, field)
            if value > budget_value:
                violations.append(
                    f"[over-budget] {name}.{field}: {value:.2f}ms > {budget_value:.2f}ms (limit)"
                )
    return violations
