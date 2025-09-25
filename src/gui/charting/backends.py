"""Chart backend implementations (Milestone 7.1)

Currently only a minimal Matplotlib backend is provided. We isolate the
imports so tests that don't require GUI context can mock or skip them.
"""

from __future__ import annotations

from typing import Sequence, Any

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

    # --- heatmap -------------------------------------------------------
    def create_heatmap(
        self,
        matrix: Sequence[Sequence[float]],
        *,
        x_labels: Sequence[str] | None = None,
        y_labels: Sequence[str] | None = None,
        title: str | None = None,
        cmap: str = "Blues",
    ) -> Any:  # QWidget instance (FigureCanvasQTAgg)
        fig = Figure(figsize=(5.2, 3.6))
        canvas = FigureCanvasQTAgg(fig)
        ax = fig.add_subplot(111)
        import numpy as _np  # local import to keep startup light

        data = _np.array(matrix, dtype=float) if matrix else _np.zeros((0, 0))
        im = ax.imshow(data, aspect="auto", interpolation="nearest", cmap=cmap)
        if x_labels:
            ax.set_xticks(range(len(x_labels)))
            ax.set_xticklabels(x_labels, rotation=90, fontsize=8)
        if y_labels:
            ax.set_yticks(range(len(y_labels)))
            ax.set_yticklabels(y_labels, fontsize=8)
        if title:
            ax.set_title(title)
        ax.figure.colorbar(im, ax=ax, fraction=0.046, pad=0.04)
        fig.tight_layout()
        return canvas
