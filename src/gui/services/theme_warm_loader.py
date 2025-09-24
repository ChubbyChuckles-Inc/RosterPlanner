"""Theme Warm-Load Prefetch Service (Milestone 5.10.69).

Precomputes derived theme data (accent palettes for a set of candidate accent
bases & variants) during idle time so that first-use interactions (switching
accent or variant) avoid on-demand computation cost.

Scope (initial):
 - Precompute accent palette derivations using existing derive_accent_palette
   for a configured list of base hex seeds.
 - Store into the ThemeManager's internal accent cache (via public setter API
   indirectly by calling set_accent_base temporarily and restoring original).
 - Debounce startup execution with a single-shot QTimer to avoid penalizing
   critical path UI initialization.

Design Considerations:
 - Non-intrusive: if ThemeManager changes before warm load fires, we still run.
 - Idempotent: skip already cached entries.
 - Safe: swallow exceptions.
 - Testable: expose `is_completed()` and allow manual trigger via `run_now()`.

Future Enhancements:
 - Prefetch full variant maps for all variants.
 - Background thread offloading if computation grows (currently cheap).
"""

from __future__ import annotations
from typing import Iterable, List
from PyQt6.QtCore import QObject, QTimer

try:
    from src.gui.design.theme_manager import ThemeManager  # type: ignore
except ImportError:  # pragma: no cover
    from gui.design.theme_manager import ThemeManager  # type: ignore
from gui.design.dynamic_accent import derive_accent_palette

__all__ = ["ThemeWarmLoader"]


class ThemeWarmLoader(QObject):
    def __init__(
        self,
        theme_manager: ThemeManager,
        *,
        delay_ms: int = 300,
        accent_seeds: Iterable[str] | None = None,
    ):
        super().__init__()
        self._tm = theme_manager
        self._delay_ms = max(0, min(delay_ms, 5000))
        self._accent_seeds: List[str] = [
            s.upper()
            for s in (accent_seeds or [theme_manager.accent_base, "#0D6EFD", "#6610F2", "#198754"])
        ]
        # Deduplicate while preserving order
        seen = set()
        ordered = []
        for s in self._accent_seeds:
            if s not in seen:
                ordered.append(s)
                seen.add(s)
        self._accent_seeds = ordered
        self._started = False
        self._completed = False
        self._timer: QTimer | None = None
        self._schedule()

    # Scheduling --------------------------------------------------------
    def _schedule(self):
        if self._delay_ms == 0:
            self._run()
            return
        self._timer = QTimer(self)
        self._timer.setSingleShot(True)
        self._timer.timeout.connect(self._run)  # type: ignore[attr-defined]
        self._timer.start(self._delay_ms)

    # Execution ---------------------------------------------------------
    def _run(self):  # pragma: no cover - wrapper calls run logic
        if self._completed:
            return
        self._started = True
        try:
            self._prefetch()
        finally:
            self._completed = True

    def _prefetch(self):
        original = self._tm.accent_base
        # Access private cache (kept minimal risk); still use derive to mimic ThemeManager logic
        cache = getattr(self._tm, "_accent_cache", {})
        for seed in self._accent_seeds:
            if seed in cache:
                continue
            try:
                palette = derive_accent_palette(seed)
                cache[seed] = palette
            except Exception:
                pass
        # Restore original active accent if necessary (no diff emission here)
        if original != self._tm.accent_base:
            try:
                self._tm.set_accent_base(original)
            except Exception:
                pass

    # Public ------------------------------------------------------------
    def is_completed(self) -> bool:
        return self._completed

    def run_now(self) -> None:
        if not self._completed:
            if self._timer:
                try:
                    self._timer.stop()
                except Exception:
                    pass
                self._timer = None
            self._run()
