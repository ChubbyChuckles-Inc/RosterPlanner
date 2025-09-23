"""Color Blindness Mode Service (Milestone 5.10.15)

Provides a lightweight stateful service storing the current simulated
color blindness mode (None / protanopia / deuteranopia). This initial
implementation only exposes mode changes and a signal-like callback
registry so views (or MainWindow) can react. Heavy pixel-level
processing is intentionally deferred; we only tag the UI with a
property that can drive future QSS or targeted transforms.
"""

from __future__ import annotations
from dataclasses import dataclass, field
from typing import Callable, List, Optional

ModeType = Optional[str]  # 'protanopia' | 'deuteranopia' | None

Callback = Callable[[ModeType, ModeType], None]

__all__ = ["ColorBlindModeService"]


@dataclass
class ColorBlindModeService:
    _mode: ModeType = None
    _callbacks: List[Callback] = field(default_factory=list)

    @property
    def mode(self) -> ModeType:
        return self._mode

    def set_mode(self, mode: ModeType) -> ModeType:
        if mode not in (None, "protanopia", "deuteranopia"):
            raise ValueError(f"Unsupported color blindness mode: {mode}")
        if mode == self._mode:
            return self._mode
        old = self._mode
        self._mode = mode
        for cb in list(self._callbacks):
            try:
                cb(old, mode)
            except Exception:
                pass
        return self._mode

    def on_change(self, callback: Callback) -> None:
        if callback not in self._callbacks:
            self._callbacks.append(callback)

    def remove_callback(self, callback: Callback) -> None:
        try:
            self._callbacks.remove(callback)
        except ValueError:
            pass
