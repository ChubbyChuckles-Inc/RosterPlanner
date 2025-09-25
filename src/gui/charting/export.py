"""Chart export & interactivity utilities (Milestone 7.7 partial).

Provides a thin helper wrapping backend export & optional tooltip enabling.
This keeps higher-level code decoupled from backend concrete APIs.
"""
from __future__ import annotations

from . import chart_registry


def export_chart(chart_widget, path: str, *, format: str = "png", dpi: int = 120) -> None:
    """Export a chart widget to disk via the backend if supported.

    Args:
        chart_widget: The canvas/widget returned in ChartResult.widget.
        path: Destination file path (existing directory required).
        format: 'png' or 'svg'.
        dpi: Raster resolution for PNG.
    """
    backend = chart_registry._backend  # type: ignore[attr-defined]
    backend.export_widget(chart_widget, path, format=format, dpi=dpi)


def enable_line_chart_tooltips(chart_widget, series, x_values=None, labels=None) -> None:  # noqa: D401
    backend = chart_registry._backend  # type: ignore[attr-defined]
    backend.enable_basic_line_tooltips(chart_widget, series, x_values, labels)
