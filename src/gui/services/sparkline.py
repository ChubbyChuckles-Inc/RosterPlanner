"""Sparkline generation service (Milestone 5.2.1).

Provides a lightweight, dependency-free way to render a tiny inline
sparkline string given a sequence of numeric values (e.g. recent
LivePZ deltas for a player). This is a placeholder for future richer
micro chart rendering (e.g., via a custom delegate or lightweight
QPainter drawing) but suffices for textual trend indication.

Design goals:
 - Pure function style for easy unit testing.
 - Graceful handling of empty / single-value sequences.
 - Stable output length equal to input length (capped at a sensible maximum
   to avoid overly wide columns—caller can truncate if needed).
 - Unicode block characters for vertical resolution (Braille blocks avoided
   for simplicity; use the common 1/8 block ramp for clarity).

Ramp chosen: "▁▂▃▄▅▆▇█" (8 levels). Values are linearly normalized between
min and max; if all values are equal, a flat mid-level bar is produced.
"""

from __future__ import annotations
from typing import Iterable, List

__all__ = ["SparklineBuilder"]


class SparklineBuilder:
    """Build unicode sparkline strings from numeric sequences.

    Usage:
        builder = SparklineBuilder()
        text = builder.build([1,5,3,9])
    """

    _RAMP = "▁▂▃▄▅▆▇█"

    def build(self, values: Iterable[int | float]) -> str:
        seq: List[float] = [float(v) for v in values]
        if not seq:
            return ""  # empty -> empty, caller can show placeholder
        if len(seq) == 1:
            # Single point -> middle ramp character (visual neutrality)
            return self._RAMP[len(self._RAMP) // 2]
        lo = min(seq)
        hi = max(seq)
        if hi == lo:
            mid_char = self._RAMP[len(self._RAMP) // 2]
            return mid_char * len(seq)
        span = hi - lo
        # Map each value linearly to ramp index
        out_chars: List[str] = []
        last_idx = len(self._RAMP) - 1
        for v in seq:
            norm = (v - lo) / span
            idx = int(round(norm * last_idx))
            if idx < 0:
                idx = 0
            elif idx > last_idx:
                idx = last_idx
            out_chars.append(self._RAMP[idx])
        return "".join(out_chars)
