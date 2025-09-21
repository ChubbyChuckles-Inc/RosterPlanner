"""Layout direction registry for RTL/LTR simulation (Milestone 0.13 partial).

This lightweight module allows the application (or tests) to flip between left-to-right
and right-to-left layout direction independent of active locale. The goal is to
surface mirroring/layout issues early before full RTL localization.

Design:
 - No Qt dependency at import time (lazy import inside `apply_qt_direction`).
 - Simple validated setter; idempotent changes allowed.
 - Python 3.8 compatible (no Pattern Matching / PEP 604 unions).
"""

from __future__ import annotations

from typing import Literal

Direction = Literal["ltr", "rtl"]
_direction: Direction = "ltr"

__all__ = [
    "get_layout_direction",
    "set_layout_direction",
    "is_rtl",
    "apply_qt_direction",
    "init_direction_from_env",
]


def get_layout_direction() -> str:
    """Return the current logical layout direction ("ltr" or "rtl")."""
    return _direction


def is_rtl() -> bool:
    """Return True if the current direction is right-to-left."""
    return _direction == "rtl"


def set_layout_direction(direction: str) -> None:
    """Set the layout direction.

    Raises:
        ValueError: if direction is not one of {"ltr", "rtl"}.
    """
    if direction not in ("ltr", "rtl"):
        raise ValueError(f"Invalid direction: {direction!r} (expected 'ltr' or 'rtl')")
    global _direction
    _direction = direction  # idempotent allowed


def apply_qt_direction(target) -> None:  # pragma: no cover - UI side effect
    """Apply current layout direction to a QApplication or QWidget-like object.

    Accepts either a QApplication (where the method is static) or any object
    providing a ``setLayoutDirection(Qt.LayoutDirection)`` method.
    Fails silently if PyQt6 is unavailable (e.g. during headless unit tests).
    """
    try:
        from PyQt6.QtCore import Qt  # type: ignore
    except Exception:
        return
    qt_dir = Qt.LayoutDirection.RightToLeft if is_rtl() else Qt.LayoutDirection.LeftToRight
    setter = getattr(target, "setLayoutDirection", None)
    if callable(setter):
        setter(qt_dir)


def init_direction_from_env(env: "dict[str, str] | None" = None) -> None:
    """Initialize direction from environment.

    If environment variable ``ROSTERPLANNER_RTL`` is set to a truthy value ("1", "true",
    "yes", "on") we switch direction to ``rtl``. This is intended for early testing
    via CI or developer shells without changing application code.
    """
    if env is None:
        import os

        env = os.environ  # type: ignore
    raw = env.get("ROSTERPLANNER_RTL")
    if not raw:
        return
    if raw.strip().lower() in {"1", "true", "yes", "on"}:
        set_layout_direction("rtl")
