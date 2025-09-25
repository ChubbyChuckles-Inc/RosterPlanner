"""Responsive layout adaptation utilities (Milestone 7.9).

Rules (initial simple set):
    - Hide legend if figure width (px) < MIN_LEGEND_WIDTH.
    - Reduce x tick labels density if tick count exceeds MAX_XTICKS_DENSE and width small.

Metadata is attached to the matplotlib Figure via a private attribute
``_rp_responsive`` so higher layers (registry) can merge it into ChartResult.meta.
"""

from __future__ import annotations

from typing import Any

MIN_LEGEND_WIDTH = 450  # px; below this we hide legend to save space
MAX_XTICKS_DENSE = 14  # if more than this and narrow figure, we thin ticks


def apply_responsive_rules(fig: Any) -> None:  # pragma: no cover - logic hit via tests
    try:
        import matplotlib.pyplot as _plt  # noqa: F401  # ensure backend registered
    except Exception:  # Matplotlib not available
        return
    try:
        width_px = fig.get_figwidth() * fig.dpi
        axes = fig.axes
    except Exception:
        return
    meta: dict[str, Any] = {"legend_hidden": False, "x_ticks_reduced": False}
    for ax in axes:
        # Legend handling
        leg = ax.get_legend()
        if leg and width_px < MIN_LEGEND_WIDTH:
            try:
                leg.remove()
                meta["legend_hidden"] = True
            except Exception:
                pass
        # X ticks thinning
        try:
            ticks = ax.get_xticks()
            if len(ticks) > MAX_XTICKS_DENSE and width_px < MIN_LEGEND_WIDTH:
                # keep every second tick label
                new_ticks = ticks[::2]
                ax.set_xticks(new_ticks)
                meta["x_ticks_reduced"] = True
        except Exception:
            pass
    # Attach aggregated metadata (if multiple axes OR logic triggered)
    fig._rp_responsive = meta  # type: ignore[attr-defined]
