"""ViewModel for Live Theme Preview Diff Panel (Milestone 5.10.34).

Separates headless diff computation from the Qt view. The panel previews
the before/after mapping of theme colors when a hypothetical change is
applied (variant switch or accent mutation) without mutating the active
theme. This enables safe experimentation prior to committing changes.

Core Responsibilities:
 - Provide snapshot of current theme mapping.
 - Compute a simulated diff for a requested variant or accent base.
 - Expose diff entries limited to changed keys only.
 - Provide revert/no-op semantics (pure functions; no side effects).

Design:
 - Consumes `ThemeService` for the current mapping and a new temporary
   `ThemeManager` instance for simulation.
 - Keeps no internal mutable state beyond the baseline snapshot so tests
   can assert deterministic outputs.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, List, Tuple, Union

from gui.services.theme_service import ThemeService
from gui.design import ThemeManager, load_tokens

__all__ = ["ThemePreviewDiffViewModel", "PreviewDiffEntry"]

PreviewDiffEntry = Tuple[str, Union[str, None], Union[str, None]]


@dataclass
class ThemePreviewDiffViewModel:
    """Compute simulated theme diffs without mutating global theme state."""

    baseline: Dict[str, str]

    @classmethod
    def capture(cls, svc: ThemeService) -> "ThemePreviewDiffViewModel":
        return cls(baseline=dict(svc.colors()))

    # Simulation API -------------------------------------------------
    def simulate_variant(self, variant: str) -> List[PreviewDiffEntry]:
        tokens = load_tokens()
        mgr = ThemeManager(tokens, variant=variant)  # type: ignore[arg-type]
        mapping = dict(mgr.active_map())
        self._augment(mapping)
        return self._diff(self.baseline, mapping)

    def simulate_accent(self, accent_hex: str) -> List[PreviewDiffEntry]:
        tokens = load_tokens()
        mgr = ThemeManager(tokens)
        mgr.set_accent_base(accent_hex)
        mapping = dict(mgr.active_map())
        self._augment(mapping)
        return self._diff(self.baseline, mapping)

    # Internal -------------------------------------------------------
    @staticmethod
    def _augment(mapping: Dict[str, str]) -> None:
        # Minimal augmentation mirroring ThemeService aliasing subset where needed
        if "background.base" in mapping and "background.primary" not in mapping:
            mapping["background.primary"] = mapping["background.base"]
        if "accent.primary" in mapping and "accent.base" not in mapping:
            mapping["accent.base"] = mapping["accent.primary"]

    @staticmethod
    def _diff(old: Dict[str, str], new: Dict[str, str]) -> List[PreviewDiffEntry]:
        keys = set(old.keys()) | set(new.keys())
        out: List[PreviewDiffEntry] = []
        for k in sorted(keys):
            ov = old.get(k)
            nv = new.get(k)
            if ov != nv:
                out.append((k, ov, nv))
        return out
