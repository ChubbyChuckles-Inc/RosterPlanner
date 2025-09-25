"""Chart backend implementations (Milestone 7.1)

Currently only a minimal Matplotlib backend is provided. We isolate the
imports so tests that don't require GUI context can mock or skip them.
"""
from __future__ import annotations

from typing import Sequence

try:  # pragma: no cover - import guarded
    from matplotlib.figure import Figure
    from matplotlib.backends.backend_qtagg import FigureCanvasQTAgg
except Exception:  # pragma: no cover - headless fallback
    Figure = object  # type: ignore
    FigureCanvasQTAgg = object  # type: ignore

from .types import ChartBackendProtocol


class MatplotlibChartBackend(ChartBackendProtocol):  # pragma: no cover - thin wrapper
    def create_line_chart(
        self,
        series: Sequence[Sequence[float]],
        *,
        labels: Sequence[str] | None = None,
        title: str | None = None,
        x_values: Sequence[float] | None = None,
    ):
        fig = Figure(figsize=(4, 2.2), tight_layout=True)
        ax = fig.add_subplot(111)
        if x_values is None:
            x_values = list(range(len(series[0]) if series else 0))
        for idx, ys in enumerate(series):
            lbl = labels[idx] if labels and idx < len(labels) else None
            ax.plot(x_values, ys, label=lbl)
        if title:
            ax.set_title(title)
        if labels:
            ax.legend()
        canvas = FigureCanvasQTAgg(fig)
        return canvas
