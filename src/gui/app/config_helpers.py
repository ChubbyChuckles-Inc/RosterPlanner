"""Helper utilities for updating persistent application configuration.

These helpers centralize mutation patterns so future validation / hooks can be
added in one place. They are GUI-framework agnostic and safe to call in tests.
"""

from __future__ import annotations

from typing import Optional
from .config_store import AppConfig

__all__ = [
    "update_last_data_dir",
    "record_window_geometry",
]


def update_last_data_dir(cfg: AppConfig, path: str | None) -> None:
    """Update last_data_dir and prepend to history if provided.

    Maintains most-recent-first ordering and uniqueness. History is lazily
    initialized.
    """
    if path is None:
        return
    cfg.last_data_dir = path
    hist = cfg.data_dir_history or []
    if path in hist:
        hist.remove(path)
    hist.insert(0, path)
    # Cap history length to reasonable size (avoid unbounded growth)
    if len(hist) > 10:
        del hist[10:]
    cfg.data_dir_history = hist


def record_window_geometry(
    cfg: AppConfig,
    *,
    x: Optional[int],
    y: Optional[int],
    w: Optional[int],
    h: Optional[int],
    maximized: bool,
    raw: str | None = None,
) -> None:
    """Persist window geometry fields.

    raw: Optional serialized blob (e.g., QByteArray encoded as base64) for more
    precise restore in future milestones.
    """
    cfg.window_x = x
    cfg.window_y = y
    cfg.window_w = w
    cfg.window_h = h
    cfg.maximized = maximized
    if raw is not None:
        cfg.window_geometry_raw = raw
