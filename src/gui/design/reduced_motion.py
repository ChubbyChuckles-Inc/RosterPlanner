"""Adaptive motion reduction utilities.

Provides a single source of truth for whether motion/animations should be
reduced (e.g. for users who prefer reduced motion for accessibility or who
run the application on resource constrained environments).

Patterns:
- Global module level state guarded by simple setter/getter (thread-safety
  not strictly required for current usage; operations are idempotent and
  extremely fast). If later contention appears, a lightweight Lock can be
  introduced without changing public API.
- Environment variable bootstrap: ``APP_PREFER_REDUCED_MOTION=1`` (or "true"
  case-insensitive) will enable reduced motion at import time. Any other
  value leaves default (False).
- Scaling: ``motion_scale()`` returns a multiplier applied to animation
  durations. When reduced motion is enabled the scale is 0.0 (i.e., skip).
  ``adjust_duration(ms)`` clamps to a minimum fallback (default 0) when
  reduced.

Public API:
- set_reduced_motion(enabled: bool) -> None
- is_reduced_motion() -> bool
- motion_scale(fallback: float = 1.0) -> float
- adjust_duration(ms: int, minimum_ms: int = 0) -> int
- temporarily_reduced_motion(force: bool = True) -> context manager

Edge Cases & Defensive Behavior:
- Setting the same value twice is harmless.
- Negative durations passed to ``adjust_duration`` are treated as 0 before
  scaling to avoid propagating invalid timings.
- ``motion_scale`` always returns a float >= 0.

Test Strategy:
- Default state is False (unless env var set for test scenario).
- Env var bootstrap respected when reloading module in isolated context.
- Toggling on/off updates queries.
- adjust_duration returns original when not reduced; minimum when reduced.
- Context manager restores previous state on normal exit and on exception.

This module is Python 3.8 compatible.
"""

from __future__ import annotations

import os
import contextlib
from typing import Iterator

__all__ = [
    "set_reduced_motion",
    "is_reduced_motion",
    "motion_scale",
    "adjust_duration",
    "temporarily_reduced_motion",
]

# Internal state
_reduced_motion_enabled: bool = False

# Bootstrap from environment
_env_value = os.getenv("APP_PREFER_REDUCED_MOTION", "").strip().lower()
if _env_value in {"1", "true", "yes", "on"}:
    _reduced_motion_enabled = True


def set_reduced_motion(enabled: bool) -> None:
    """Set the global reduced motion preference.

    Idempotent; simply updates module state.
    """
    global _reduced_motion_enabled
    _reduced_motion_enabled = bool(enabled)


def is_reduced_motion() -> bool:
    """Return whether reduced motion is currently enabled."""
    return _reduced_motion_enabled


def motion_scale(fallback: float = 1.0) -> float:
    """Return a scale multiplier for motion-related durations.

    When reduced motion is enabled returns 0.0 meaning animations should
    effectively be disabled (instant). Otherwise returns ``fallback``.
    ``fallback`` must be > 0.
    """
    if fallback <= 0:
        raise ValueError("fallback scale must be > 0")
    return 0.0 if _reduced_motion_enabled else float(fallback)


def adjust_duration(ms: int, minimum_ms: int = 0) -> int:
    """Adjust a duration (milliseconds) based on reduced motion setting.

    If reduced motion is enabled returns ``minimum_ms`` (default 0). Otherwise
    returns the original ``ms`` (clamped to >= 0). ``minimum_ms`` is clamped
    to >= 0 as well.
    """
    if minimum_ms < 0:
        minimum_ms = 0
    if ms < 0:
        ms = 0
    return minimum_ms if _reduced_motion_enabled else ms


@contextlib.contextmanager
def temporarily_reduced_motion(force: bool = True) -> Iterator[None]:
    """Context manager to temporarily override reduced motion preference.

    Parameters
    ----------
    force: bool
        If True (default) forces reduced motion ON within the context.
        If False forces it OFF within the context (useful for testing
        actual motion flows while a global preference is set).
    """
    prev = _reduced_motion_enabled
    try:
        set_reduced_motion(True if force else False)
        yield
    finally:
        # Restore prior state unconditionally
        set_reduced_motion(prev)
