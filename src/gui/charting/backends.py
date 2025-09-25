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

    # --- interactive helpers -----------------------------------------
    def enable_basic_line_tooltips(
        self,
        canvas,
        series: Sequence[Sequence[float]],
        x_values: Sequence[float] | None,
        labels: Sequence[str] | None,
    ) -> None:  # pragma: no cover - interactive GUI feature
        try:
            import math

            fig = canvas.figure  # type: ignore[attr-defined]
            ax = fig.axes[0]
            if x_values is None and series and series[0]:
                x_values = list(range(len(series[0])))
            scatters = []
            for idx, ys in enumerate(series):
                xs = x_values if x_values is not None else list(range(len(ys)))
                scatter = ax.scatter(xs, ys, s=10, alpha=0)  # invisible hit targets
                scatters.append(
                    (
                        scatter,
                        ys,
                        xs,
                        labels[idx] if labels and idx < len(labels) else f"Series {idx+1}",
                    )
                )
            annot = ax.annotate(
                "",
                xy=(0, 0),
                xytext=(10, 10),
                textcoords="offset points",
                bbox={"boxstyle": "round", "fc": "w", "alpha": 0.8},
                arrowprops={"arrowstyle": "->"},
            )
            annot.set_visible(False)

            def _update(event):  # noqa: D401
                vis = annot.get_visible()
                if event.inaxes != ax:
                    if vis:
                        annot.set_visible(False)
                        canvas.draw_idle()
                    return
                # simple nearest-point search
                best = None
                best_dist = 12  # pixels threshold
                for scatter, ys, xs, label in scatters:
                    cont, ind = scatter.contains(event)
                    if not cont:
                        # compute nearest manually (fallback)
                        if not xs:
                            continue
                        # rough pixel distance via data coords approximation
                        for i, (xv, yv) in enumerate(zip(xs, ys)):
                            dx = event.xdata - xv
                            dy = event.ydata - yv
                            d = math.hypot(dx, dy)
                            if d < best_dist:
                                best_dist = d
                                best = (xv, yv, label, i)
                        continue
                    # use first index
                    i = ind["ind"][0]
                    best = (xs[i], ys[i], label, i)
                    best_dist = 0
                if best:
                    xv, yv, label, i = best
                    annot.xy = (xv, yv)
                    annot.set_text(f"{label}\nIndex {i}: {yv}")
                    annot.set_visible(True)
                    canvas.draw_idle()
                elif vis:
                    annot.set_visible(False)
                    canvas.draw_idle()

            fig.canvas.mpl_connect("motion_notify_event", _update)
        except Exception:  # silent fallback
            return

    def export_widget(self, canvas, path: str, *, format: str = "png", dpi: int = 120) -> None:
        try:
            fig = canvas.figure  # type: ignore[attr-defined]
        except Exception as e:  # pragma: no cover - invalid canvas
            raise ValueError("Unsupported canvas type for export") from e
        if format.lower() not in {"png", "svg"}:
            raise ValueError("format must be 'png' or 'svg'")
        fig.savefig(path, format=format.lower(), dpi=dpi if format.lower() == "png" else None)
