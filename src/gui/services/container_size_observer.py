"""Container Size Observer Utilities (Milestone 5.10.39).

Provides a lightweight, testable abstraction for observing widget size changes
and emitting responsive density & typography adjustment hints without tightly
coupling to specific views.

Goals:
 - Centralize breakpoint logic (width-driven) for adaptive density / typography.
 - Avoid per-widget ad-hoc resizeEvent overrides scattered across code.
 - Offer pure function for breakpoint evaluation (unit tested headlessly).
 - Integrate with existing `DensityService` only via published events, not direct mutation.

Design:
 - Breakpoints (width):
     < 800px  => profile = "narrow"   (suggest compact density + small typography scale)
     800-1199 => profile = "medium"   (comfortable density, base typography)
     >=1200   => profile = "wide"     (comfortable density, larger typography accent)
 - Mapping to recommendations (density, type_scale_multiplier)
 - Observer stores last profile per widget to suppress duplicate emissions.
 - Emits `container_profile_changed` event on the global EventBus with payload:
       {"object": <QObject>, "profile": str, "density": str, "type_scale": float}
 - A future listener can subscribe and coordinate applying density changes if desired.

This keeps Milestone 5.10.39 self‑contained: feature delivers utilities & events,
but does not auto-change density (avoid surprising user). A follow-up milestone
can add an adaptive controller if toggled by a preference.
"""

from __future__ import annotations
from dataclasses import dataclass
from typing import Dict, Tuple, Optional

try:  # Qt optional for headless tests
    from PyQt6.QtCore import QObject, QEvent
except Exception:  # pragma: no cover
    QObject = object  # type: ignore
    QEvent = object  # type: ignore

from .service_locator import services
from .event_bus import EventBus

BreakpointProfile = str


@dataclass(frozen=True)
class ContainerProfile:
    profile: BreakpointProfile
    density: str
    type_scale: float


def evaluate_profile(width: int) -> ContainerProfile:
    """Pure function mapping width -> ContainerProfile.

    Rules (subject to future tuning):
      <800: narrow / compact / 0.92
      800-1199: medium / comfortable / 1.0
      >=1200: wide / comfortable / 1.05
    """
    if width < 0:
        width = 0
    if width < 800:
        return ContainerProfile("narrow", "compact", 0.92)
    if width < 1200:
        return ContainerProfile("medium", "comfortable", 1.0)
    return ContainerProfile("wide", "comfortable", 1.05)


class _ResizeFilter(QObject):  # pragma: no cover - trivial Qt glue
    def __init__(self, parent, observer: "ContainerSizeObserver"):
        super().__init__(parent)
        self._observer = observer

    def eventFilter(self, watched, event):  # type: ignore[override]
        try:
            from PyQt6.QtCore import QEvent as _QEvent  # local import to allow headless tests

            if event.type() == _QEvent.Type.Resize:  # type: ignore[attr-defined]
                self._observer._on_resize(watched)
        except Exception:
            pass
        return False


class ContainerSizeObserver:
    """Registers widgets for breakpoint-based profile evaluation.

    Only emits events when profile changes.
    """

    def __init__(self):
        self._profiles: Dict[int, BreakpointProfile] = {}
        self._filters: Dict[int, QObject] = {}

    def observe(self, widget: QObject):  # pragma: no cover - thin Qt layer
        wid = id(widget)
        if wid in self._filters:
            return
        try:
            filt = _ResizeFilter(widget, self)
            widget.installEventFilter(filt)  # type: ignore[attr-defined]
            self._filters[wid] = filt
            # Evaluate immediately using current width if possible
            self._on_resize(widget)
        except Exception:
            pass

    # Internal callback after resize
    def _on_resize(self, widget):  # pragma: no cover - depends on real Qt resize
        try:
            width = widget.width()  # type: ignore[attr-defined]
        except Exception:
            return
        profile = evaluate_profile(width)
        wid = id(widget)
        if self._profiles.get(wid) == profile.profile:
            return  # no change
        self._profiles[wid] = profile.profile
        # Publish event
        try:
            bus = services.get_typed("event_bus", EventBus)
            bus.publish(
                "container_profile_changed",
                {
                    "object": widget,
                    "profile": profile.profile,
                    "density": profile.density,
                    "type_scale": profile.type_scale,
                },
            )
        except Exception:
            pass


def get_container_size_observer() -> ContainerSizeObserver:
    obs = services.try_get("container_size_observer")
    if obs is None:
        obs = ContainerSizeObserver()
        services.register("container_size_observer", obs)
    return obs


__all__ = [
    "ContainerSizeObserver",
    "evaluate_profile",
    "get_container_size_observer",
    "ContainerProfile",
]
