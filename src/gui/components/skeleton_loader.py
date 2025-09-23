"""Skeleton Loader Widget (Milestone 5.10.10 partial).

Provides a lightweight, theme-aware placeholder shown while data is loading.
Currently renders simple QLabel-based blocks sized according to the referenced
`SkeletonVariant` shapes. Future enhancements may replace this with a custom
painted widget (shimmer effect, animations, token-driven motion).

Design Principles:
 - No heavy dependencies (pure Qt widgets)
 - Testable: expose variant name & active flag
 - Swappable: views can show/hide skeleton without altering layout structure

API:
    loader = SkeletonLoaderWidget('table-row', rows=5)
    loader.start() / loader.stop()
    loader.is_active()

Integration Plan (5.10.10):
 - TeamDetailView: show table-row skeleton rows until bundle set
 - DivisionTableView: show table-row skeleton rows until standings provided
 - Future: shimmer animation leveraging motion tokens (duration/easing)
"""

from __future__ import annotations
from typing import List, Optional
from PyQt6.QtWidgets import QWidget, QVBoxLayout, QLabel, QSizePolicy
from PyQt6.QtCore import Qt

from gui.design.skeletons import get_skeleton_variant, SkeletonVariant

__all__ = ["SkeletonLoaderWidget"]


class SkeletonLoaderWidget(QWidget):
    """Simple vertical stack of placeholder blocks derived from a SkeletonVariant.

    Parameters
    ----------
    variant_name: str
        Name of the registered skeleton variant (e.g., 'table-row').
    rows: int
        Number of repeated variant rows to render.
    """

    def __init__(self, variant_name: str, rows: int = 3, parent: Optional[QWidget] = None):
        super().__init__(parent)
        self._variant_name = variant_name
        self._rows = max(1, rows)
        self._variant: SkeletonVariant = get_skeleton_variant(variant_name)
        self._active = False
        self.setObjectName("skeletonLoader")
        self._build_ui()

    # UI -----------------------------------------------------------------
    def _build_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(6)
        for _ in range(self._rows):
            row_container = self._build_row()
            layout.addWidget(row_container)
        layout.addStretch(1)

    def _build_row(self) -> QWidget:
        from PyQt6.QtWidgets import QHBoxLayout

        w = QWidget(self)
        w.setObjectName("skeletonRow")
        hl = QHBoxLayout(w)
        hl.setContentsMargins(0, 0, 0, 0)
        hl.setSpacing(8)
        for shape in self._variant.shapes:
            block = QLabel("")
            block.setObjectName(f"skeleton_{shape['type']}")
            # Apply fixed size hints based on nominal dimensions
            block.setFixedHeight(int(shape.get("h", 8)))
            block.setFixedWidth(int(shape.get("w", 40)))
            block.setSizePolicy(QSizePolicy.Policy.Fixed, QSizePolicy.Policy.Fixed)
            # Use style property for sub-role to allow QSS targeting
            block.setProperty("skelStyle", shape.get("style", "primary"))
            block.setProperty("skelVariant", self._variant_name)
            hl.addWidget(block)
        hl.addStretch(1)
        return w

    # Control -------------------------------------------------------------
    def start(self):
        self.show()
        self._active = True

    def stop(self):
        self.hide()
        self._active = False

    # Accessors -----------------------------------------------------------
    def variant_name(self) -> str:
        return self._variant_name

    def is_active(self) -> bool:
        return self._active
