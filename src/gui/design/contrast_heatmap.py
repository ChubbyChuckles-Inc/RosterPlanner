"""Contrast Heatmap Analyzer (Milestone 5.10.35).

Provides headless logic to compute contrast ratings for foreground/background
pairs supplied by a sampling adapter (e.g., a QWidget walker). The GUI overlay
itself (optional future addition) can color-code low-contrast regions.

We avoid direct QWidget dependencies here to keep logic unit testable.

Usage:

    sampler = list(sample_pairs(...)) -> Iterable[ContrastSampleInput]
    report = analyze_contrast(sampler)

Exports:
 - ContrastSampleInput dataclass (id, fg, bg, meta)
 - ContrastIssue dataclass (id, ratio, level, required, fg, bg, meta)
 - ContrastReport dataclass (issues, summary dict)
 - analyze_contrast(inputs, min_normal=4.5, min_large=3.0)

WCAG 2.2 thresholds used by default: 4.5 normal text, 3.0 large text. Caller
can override thresholds (e.g., for debug scenarios). Large-text detection can
be signaled via meta flag `large_text=True`.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable, List, Dict, Any

from .contrast import contrast_ratio

__all__ = [
    "ContrastSampleInput",
    "ContrastIssue",
    "ContrastReport",
    "analyze_contrast",
]


@dataclass(frozen=True)
class ContrastSampleInput:
    id: str
    fg: str
    bg: str
    meta: Dict[str, Any] | None = None


@dataclass(frozen=True)
class ContrastIssue:
    id: str
    ratio: float
    required: float
    level: str  # "fail" or "pass"
    fg: str
    bg: str
    meta: Dict[str, Any] | None = None


@dataclass(frozen=True)
class ContrastReport:
    issues: List[ContrastIssue]
    summary: Dict[str, Any]

    @property
    def failing(self) -> List[ContrastIssue]:  # noqa: D401 - simple delegator
        return [i for i in self.issues if i.level == "fail"]


def _norm_hex(color: str) -> str:
    if not color:
        return color
    c = color.strip()
    if len(c) == 4 and c.startswith("#"):
        # Expand shorthand #RGB -> #RRGGBB
        r, g, b = c[1], c[2], c[3]
        return f"#{r}{r}{g}{g}{b}{b}".upper()
    return c.upper()


def analyze_contrast(
    inputs: Iterable[ContrastSampleInput],
    *,
    min_normal: float = 4.5,
    min_large: float = 3.0,
) -> ContrastReport:
    issues: List[ContrastIssue] = []
    total = 0
    failing = 0
    for sample in inputs:
        total += 1
        fg = _norm_hex(sample.fg)
        bg = _norm_hex(sample.bg)
        try:
            ratio = contrast_ratio(fg, bg)
        except Exception:
            # treat as failure with ratio=0
            ratio = 0.0
        large = bool(sample.meta.get("large_text")) if sample.meta else False
        required = min_large if large else min_normal
        level = "pass" if ratio >= required else "fail"
        if level == "fail":
            failing += 1
        issues.append(
            ContrastIssue(
                id=sample.id,
                ratio=round(ratio, 3),
                required=required,
                level=level,
                fg=fg,
                bg=bg,
                meta=sample.meta or {},
            )
        )
    summary = {
        "total": total,
        "failing": failing,
        "pass_rate": 0.0 if total == 0 else round((total - failing) / total, 3),
        "threshold_normal": min_normal,
        "threshold_large": min_large,
    }
    return ContrastReport(issues=issues, summary=summary)
