"""Accessibility Focus Order Visual Path Overlay (Milestone 5.10.65).

Provides a developer-facing overlay that renders the current focus traversal
order of focusable widgets within a given root window. This helps audit
whether the visual left-to-right / top-to-bottom order matches the logical
Tab order for keyboard accessibility.

Strategy
--------
We approximate intended traversal order by sorting focusable, visible widgets
by their top-left global (y, x) coordinates. This heuristic is deterministic
and works well for grid / flow layouts. (Future enhancement: integrate actual
Qt tab chain via `QWidget.nextInFocusChain()` and compare.)

Public API
----------
compute_focus_order(root: QWidget) -> list[QWidget]
FocusOrderOverlayService.toggle(root: QWidget) -> None
FocusOrderOverlayService.hide() -> None

Painting
--------
The overlay is a transparent, mouse-click-through widget that draws a numbered
badge over each focusable widget center plus connecting lines in sequence.

This service is intentionally *not* automatically registered; it can be
instantiated ad‑hoc in dev tools / debug actions.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import List, Optional

from PyQt6.QtCore import Qt, QPoint, QRect
from PyQt6.QtGui import QPainter, QPen, QBrush, QColor, QFont
from PyQt6.QtWidgets import QWidget

__all__ = [
    "compute_focus_order",
    "FocusOrderOverlayService",
]


def _is_focusable(w: QWidget) -> bool:
    if not w.isVisible():
        return False
    policy = w.focusPolicy()
    return policy != Qt.FocusPolicy.NoFocus


def compute_focus_order(root: QWidget) -> List[QWidget]:
    """Return deterministic list of focusable widgets under ``root``.

    Order heuristic: sort by (global_y, global_x). Excludes the root itself
    unless it is explicitly focusable.
    """
    widgets: List[QWidget] = []
    for w in root.findChildren(QWidget):  # recursive
        if _is_focusable(w):
            widgets.append(w)
    # Sort by global screen position
    widgets.sort(key=lambda w: (w.mapToGlobal(QPoint(0, 0)).y(), w.mapToGlobal(QPoint(0, 0)).x()))
    return widgets


class _FocusOrderOverlay(QWidget):
    """Transparent overlay that draws the focus order path."""

    def __init__(self, root: QWidget, widgets: List[QWidget]):
        super().__init__(root)
        self._widgets = widgets
        self.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents, True)
        self.setAttribute(Qt.WidgetAttribute.WA_NoSystemBackground, True)
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground, True)
        self.setObjectName("FocusOrderOverlay")
        self._reposition()
        self.show()

    def _reposition(self):
        if self.parent() is not None:
            pr: QWidget = self.parent()  # type: ignore
            self.setGeometry(QRect(0, 0, pr.width(), pr.height()))

    def refresh(self, widgets: List[QWidget]):
        self._widgets = widgets
        self._reposition()
        self.update()

    def paintEvent(self, event):  # type: ignore[override]
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)

        # Draw connecting path first
        pen = QPen(QColor(0, 122, 204, 180), 2)
        painter.setPen(pen)
        for i in range(len(self._widgets) - 1):
            a = self._center(self._widgets[i])
            b = self._center(self._widgets[i + 1])
            painter.drawLine(a, b)

        # Draw numbered badges
        font = QFont()
        font.setPointSize(8)
        painter.setFont(font)
        for idx, w in enumerate(self._widgets, start=1):
            c = self._center(w)
            radius = 10
            painter.setBrush(QBrush(QColor(0, 0, 0, 170)))
            painter.setPen(Qt.PenStyle.NoPen)
            painter.drawEllipse(c, radius, radius)
            painter.setPen(QPen(QColor("white")))
            text = str(idx)
            tw = painter.fontMetrics().horizontalAdvance(text)
            th = painter.fontMetrics().height()
            painter.drawText(c.x() - tw / 2, c.y() + th / 4, text)

    def _center(self, w: QWidget):
        # map center point relative to overlay
        r = w.rect()
        local_center = w.mapTo(self, r.center())
        return local_center


class FocusOrderOverlayService:
    """Manage lifecycle of the focus order overlay for a root window."""

    def __init__(self):
        self._overlay: Optional[_FocusOrderOverlay] = None
        self._root: Optional[QWidget] = None

    def toggle(self, root: QWidget):
        if self._overlay and self._overlay.isVisible():
            self.hide()
            return
        self._root = root
        order = compute_focus_order(root)
        if self._overlay is None:
            self._overlay = _FocusOrderOverlay(root, order)
        else:
            self._overlay.setParent(root)
            self._overlay.refresh(order)
            self._overlay.show()

    def refresh(self):
        if self._overlay and self._root:
            self._overlay.refresh(compute_focus_order(self._root))

    def hide(self):
        if self._overlay:
            self._overlay.hide()

    def is_visible(self) -> bool:
        return bool(self._overlay and self._overlay.isVisible())
