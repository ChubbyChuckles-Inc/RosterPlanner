"""GUI components package.

Exports component gallery registration API (internal QA tooling). Future
components (buttons, tables, etc.) will live in submodules.
"""

from __future__ import annotations

from .gallery import (
    register_demo,
    list_demos,
    get_demo,
    clear_demos,
    build_gallery_window,
)

__all__ = [
    "register_demo",
    "list_demos",
    "get_demo",
    "clear_demos",
    "build_gallery_window",
]
