"""Chart registry (Milestone 7.1)

Allows registering logical chart types decoupled from concrete backend.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Callable, Dict, Any

from .types import ChartRequest, ChartResult
from .backends import MatplotlibChartBackend


@dataclass
class ChartType:
    chart_type: str
    builder: Callable[[ChartRequest, MatplotlibChartBackend], ChartResult]
    description: str


class ChartRegistry:
    def __init__(self) -> None:
        self._types: Dict[str, ChartType] = {}
        self._backend = MatplotlibChartBackend()

    def register(self, chart_type: str, builder, description: str) -> None:
        if chart_type in self._types:
            raise ValueError(f"Chart type already registered: {chart_type}")
        self._types[chart_type] = ChartType(chart_type, builder, description)

    def build(self, req: ChartRequest) -> ChartResult:
        ct = self._types.get(req.chart_type)
        if ct is None:
            raise KeyError(f"Unknown chart type: {req.chart_type}")
        return ct.builder(req, self._backend)

    def list_types(self) -> Dict[str, str]:
        return {k: v.description for k, v in self._types.items()}


chart_registry = ChartRegistry()


def register_chart_type(chart_type: str, builder, description: str) -> None:
    chart_registry.register(chart_type, builder, description)


# ---------------- Built-in basic line chart -----------------------------

def _basic_line_builder(req: ChartRequest, backend: MatplotlibChartBackend) -> ChartResult:
    data = req.data
    if not isinstance(data, dict):
        raise TypeError("Basic line chart expects dict with 'series' key")
    series = data.get("series")
    if not series:
        raise ValueError("No series provided")
    labels = data.get("labels")
    x_values = data.get("x")
    widget = backend.create_line_chart(series, labels=labels, title=(req.options or {}).get("title"), x_values=x_values)
    return ChartResult(widget=widget, meta={"series_count": len(series)})

register_chart_type(
    "line.basic", _basic_line_builder, "Basic multi-series line chart"
)
