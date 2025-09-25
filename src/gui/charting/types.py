"""Core charting types (Milestone 7.1)."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict, Protocol, Sequence, Optional


@dataclass(frozen=True)
class ChartRequest:
    """Represents a logical chart request.

    Attributes:
        chart_type: Identifier registered in the chart registry (e.g. 'line.basic').
        data: Arbitrary payload (dict or list) understood by the chart builder.
        options: Optional rendering / style hints (colors, title, axes labels).
    """

    chart_type: str
    data: Any
    options: Optional[Dict[str, Any]] = None


@dataclass
class ChartResult:
    """Represents the outcome of building a chart.

    For matplotlib backend this will hold a QWidget embedding the canvas.
    """

    widget: Any  # QWidget (Qt type avoided to keep tests headless)
    meta: Dict[str, Any]


class ChartBackendProtocol(Protocol):  # pragma: no cover - structural only
    """Protocol all chart backends must implement."""

    def create_line_chart(
        self,
        series: Sequence[Sequence[float]],
        *,
        labels: Sequence[str] | None = None,
        title: str | None = None,
        x_values: Sequence[float] | None = None,
    ) -> Any:  # QWidget
        ...
