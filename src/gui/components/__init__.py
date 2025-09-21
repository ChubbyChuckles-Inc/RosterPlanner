"""GUI components package.

Contains reusable UI widgets & supporting infrastructure. Presently exposes
only the internal component gallery registration API used for visual QA.

Stability:
 - Gallery API is internal (alpha); subject to change when component set expands.
 - Future public widgets will be documented individually with maturity levels.
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
