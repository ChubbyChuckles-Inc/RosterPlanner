"""Dock Styling Helpers (Milestone 2.6)

Provides small utilities to enhance visual affordances for dock widget dragging
and docking previews without introducing heavy dependencies.

Features:
 - Custom title bar widget with subtle grip indicator (3 vertical dots)
 - Optional semi-transparent overlay activation API for future docking preview

Design Considerations:
 - Keep logic optional: if PyQt features missing, gracefully no-op.
 - Avoid stylesheet bloat; use simple palette / QPainter drawing.
"""

from __future__ import annotations
from typing import Optional

try:  # pragma: no cover
    from PyQt6.QtWidgets import QWidget, QHBoxLayout, QLabel, QDockWidget
    from PyQt6.QtCore import Qt
    from PyQt6.QtGui import QPainter, QPen, QColor
except Exception:  # pragma: no cover
    QWidget = object  # type: ignore
    QHBoxLayout = object  # type: ignore
    QLabel = object  # type: ignore
    QDockWidget = object  # type: ignore

__all__ = ["DockStyleHelper"]


class _GripWidget(QWidget):  # pragma: no cover (visual component)
    def __init__(self):
        super().__init__()
        self.setFixedWidth(14)
        self.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents, True)

    def paintEvent(self, event):  # type: ignore[override]
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        base = self.palette().color(self.backgroundRole())
        dot_color = QColor(base)
        dot_color = dot_color.darker(140)
        pen = QPen(dot_color)
        pen.setWidth(2)
        p.setPen(pen)
        # Draw three vertically centered dots
        w = self.width() // 2
        h = self.height()
        centers = [h * 0.35, h * 0.5, h * 0.65]
        for cy in centers:
            p.drawPoint(w, int(cy))
        p.end()


class DockStyleHelper:
    def create_title_bar(self, dock):  # pragma: no cover
        """Attach a custom title bar with grip indicator.
        Silently no-ops if QWidget not real.
        """
        if not isinstance(dock, QDockWidget):  # type: ignore
            return
        title = QWidget()
        lay = QHBoxLayout(title)
        lay.setContentsMargins(4, 2, 4, 2)
        grip = _GripWidget()
        label = QLabel(dock.windowTitle())
        label.setObjectName("DockTitleLabel")
        lay.addWidget(grip)
        lay.addWidget(label)
        lay.addStretch(1)
        dock.setTitleBarWidget(title)

    def apply_to_existing_docks(self, parent):  # pragma: no cover
        if not hasattr(parent, "findChildren"):
            return
        docks = parent.findChildren(QDockWidget)  # type: ignore
        for d in docks:
            self.create_title_bar(d)

    # Placeholder overlay API for future refinement
    def show_overlay(self, parent):  # pragma: no cover
        # Future: add semi-transparent overlay showing target areas
        pass

    def hide_overlay(self, parent):  # pragma: no cover
        pass
