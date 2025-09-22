"""Motion integration helpers (Milestone 5.10.5).

Bridges design motion tokens (durations + easing curves) with PyQt6
`QPropertyAnimation` / `QParallelAnimationGroup` to provide:

 - Dock show/hide fade + subtle vertical translate
 - DocumentArea tab change cross-fade (previous active to new active)

The helpers are intentionally lightweight, returning configured animation
objects that the caller starts. This keeps logic testable: in tests we
can inspect duration/easing/target properties without running an event loop.

If PyQt6 is not available (headless tests), factory functions degrade
gracefully by returning ``None``.
"""

from __future__ import annotations

from typing import Optional, Any

try:  # Runtime import guarded for headless test environments
    from PyQt6.QtCore import QEasingCurve, QPropertyAnimation, QByteArray, QParallelAnimationGroup
    from PyQt6.QtWidgets import QWidget

    _QT_AVAILABLE = True
except Exception:  # pragma: no cover
    QEasingCurve = object  # type: ignore
    QPropertyAnimation = object  # type: ignore
    QParallelAnimationGroup = object  # type: ignore
    QWidget = object  # type: ignore
    _QT_AVAILABLE = False

from .motion import get_duration_ms, get_easing_curve
from .loader import load_tokens

__all__ = [
    "create_dock_show_animation",
    "create_dock_hide_animation",
    "create_tab_crossfade_animation",
]


def _qeasing_from_tuple(values):  # placeholder for future precise mapping
    return None


def _apply_easing(anim: "QPropertyAnimation", easing_tuple):  # type: ignore[name-defined]
    if not _QT_AVAILABLE:
        return
    # Fallback: map cubic-bezier to built-in custom curve; PyQt6 lacks direct cubic-bezier API
    # We approximate by picking a near built-in or leaving default. (Advanced mapping later.)
    # For now we ignore custom numeric control points to keep deterministic; future: implement via QEasingCurve.cubicBezierSpline (PyQt6 6.6+)
    anim.setEasingCurve(QEasingCurve.Type.InOutCubic)  # pragmatic default


def _duration(name: str) -> int:
    return get_duration_ms(load_tokens(), name)


def create_dock_show_animation(dock) -> Optional[Any]:
    if not _QT_AVAILABLE:
        return None
    from PyQt6.QtWidgets import QWidget as _QW  # local to avoid mypy mismatch

    if not isinstance(dock, _QW):  # defensive for tests using dummy stub
        return None
    group = QParallelAnimationGroup(dock)
    # Opacity (requires WA_TranslucentBackground support; fallback skip if property absent)
    try:
        fade = QPropertyAnimation(dock, QByteArray(b"windowOpacity"))
        fade.setStartValue(0.0)
        fade.setEndValue(1.0)
        fade.setDuration(_duration("subtle"))
        _apply_easing(fade, get_easing_curve(load_tokens(), "standard"))
        group.addAnimation(fade)
    except Exception:
        pass
    # Slight translate upward (geometry y - 12px)
    try:
        start_geo = dock.geometry()
        end_geo = dock.geometry()
        offset = 12
        start_geo.moveTop(start_geo.top() + offset)
        move = QPropertyAnimation(dock, QByteArray(b"geometry"))
        move.setStartValue(start_geo)
        move.setEndValue(end_geo)
        move.setDuration(_duration("subtle"))
        _apply_easing(move, get_easing_curve(load_tokens(), "decelerate"))
        group.addAnimation(move)
    except Exception:
        pass
    return group


def create_dock_hide_animation(dock) -> Optional[Any]:
    if not _QT_AVAILABLE:
        return None
    from PyQt6.QtWidgets import QWidget as _QW  # local import

    if not isinstance(dock, _QW):
        return None
    group = QParallelAnimationGroup(dock)
    try:
        fade = QPropertyAnimation(dock, QByteArray(b"windowOpacity"))
        fade.setStartValue(1.0)
        fade.setEndValue(0.0)
        fade.setDuration(_duration("subtle"))
        _apply_easing(fade, get_easing_curve(load_tokens(), "accelerate"))
        group.addAnimation(fade)
    except Exception:
        pass
    return group


def create_tab_crossfade_animation(old, new) -> Optional[Any]:
    if not _QT_AVAILABLE:
        return None
    from PyQt6.QtWidgets import QWidget as _QW

    if not isinstance(old, _QW) or not isinstance(new, _QW):
        return None
    group = QParallelAnimationGroup(new)
    try:
        fade_out = QPropertyAnimation(old, QByteArray(b"windowOpacity"))
        fade_out.setStartValue(1.0)
        fade_out.setEndValue(0.0)
        fade_out.setDuration(_duration("instant"))
        _apply_easing(fade_out, get_easing_curve(load_tokens(), "accelerate"))
        group.addAnimation(fade_out)
    except Exception:
        pass
    try:
        fade_in = QPropertyAnimation(new, QByteArray(b"windowOpacity"))
        fade_in.setStartValue(0.0)
        fade_in.setEndValue(1.0)
        fade_in.setDuration(_duration("subtle"))
        _apply_easing(fade_in, get_easing_curve(load_tokens(), "decelerate"))
        group.addAnimation(fade_in)
    except Exception:
        pass
    return group
