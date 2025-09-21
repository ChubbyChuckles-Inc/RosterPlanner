"""Live theming stress test script (Milestone 0.32).

Provides a pure-logic utility to rapidly iterate theme variants & dynamic
accent bases to surface potential state management or derivation issues.

Usage pattern (future GUI integration):
    report = run_theme_stress(tokens, iterations=50)
    if report.errors:
        # surface in diagnostics panel

Design:
- Avoid real timing delays; this is logic-only. GUI layer can choose to sleep.
- Accept `DesignTokens` + optional list of accent bases. If not provided, derive
  a small palette by sampling hue shifts.
- Toggle variant each iteration (default <-> high-contrast if supported).
- Record diff sizes and any exceptions (captured without raising).
- Deterministic order for reproducibility (sorted accent bases, fixed cycling).

Extensible: Future additions can include QSS generation latency metrics & memory
measurement hooks.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import List, Sequence, Dict, Any

from .loader import DesignTokens
from .theme_manager import ThemeManager

__all__ = ["ThemeStressReport", "run_theme_stress"]


@dataclass(frozen=True)
class ThemeStressReport:
    iterations: int
    accent_bases: Sequence[str]
    diff_counts: List[int]
    errors: List[str]
    meta: Dict[str, Any] = field(default_factory=dict)

    def total_errors(self) -> int:
        return len(self.errors)


def _derive_default_accents(base: str = "#3D8BFD") -> List[str]:
    # crude generation: rotate through a simple set of distinct hues
    # Use canonical accessible-ish accent anchors.
    return sorted({base.upper(), "#D6336C", "#0CA678", "#FD7E14", "#7048E8"})


def run_theme_stress(
    tokens: DesignTokens,
    *,
    iterations: int = 25,
    accent_bases: Sequence[str] | None = None,
) -> ThemeStressReport:
    if iterations < 1:
        raise ValueError("iterations must be >= 1")
    accents = list(accent_bases) if accent_bases else _derive_default_accents()
    accents.sort()

    manager = ThemeManager(tokens)
    diff_counts: List[int] = []
    errors: List[str] = []
    variant_cycle = (
        ["default", "high-contrast"] if tokens.is_high_contrast_supported() else ["default"]
    )

    for i in range(iterations):
        # Accent change
        try:
            new_accent = accents[i % len(accents)]
            diff = manager.set_accent_base(new_accent)
            diff_counts.append(len(diff.changed))
        except Exception as ex:  # noqa: BLE001 capture any logic errors
            errors.append(f"accent:{i}:{type(ex).__name__}:{ex}")
        # Variant toggle
        try:
            v = variant_cycle[i % len(variant_cycle)]
            diff_v = manager.set_variant(v)  # will be empty if same as current
            if diff_v.changed:
                diff_counts.append(len(diff_v.changed))
        except Exception as ex:  # noqa: BLE001
            errors.append(f"variant:{i}:{type(ex).__name__}:{ex}")

    return ThemeStressReport(
        iterations=iterations,
        accent_bases=accents,
        diff_counts=diff_counts,
        errors=errors,
        meta={"variant_cycle": variant_cycle},
    )
