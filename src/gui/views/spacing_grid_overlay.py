from __future__ import annotations

from typing import List

try:  # pragma: no cover - Qt import guard
    from PyQt6.QtCore import Qt, QRect, QSize
    from PyQt6.QtGui import QPainter, QPen, QColor
    from PyQt6.QtWidgets import QWidget
except Exception:  # pragma: no cover
    Qt = object  # type: ignore
    QRect = object  # type: ignore
    QSize = object  # type: ignore
    QPainter = object  # type: ignore
    QPen = object  # type: ignore
    QColor = object  # type: ignore
    QWidget = object  # type: ignore

DEFAULT_SPACING = 8
MIN_SPACING = 2
MAX_SPACING = 64


def clamp_spacing(value: int) -> int:
    if value < MIN_SPACING:
        return MIN_SPACING
    if value > MAX_SPACING:
        return MAX_SPACING
    return value


def generate_grid_lines(width: int, height: int, spacing: int) -> List[int]:
    spacing = clamp_spacing(spacing)
    if width < 0:
        width = 0
    if height < 0:
        height = 0
    # We only return positions (one-dimensional) sufficient for tests; painting computes both axes.
    count = max(width, height) // spacing
    return [i * spacing for i in range(count + 1)]


class SpacingGridOverlay(QWidget):  # pragma: no cover - painting not unit tested
    """Semi-transparent overlay showing the 8px (configurable) baseline grid.

    Lightweight; only active when visible. Lines painted using current palette text color with low alpha.
    """

    def __init__(self, parent=None):
        super().__init__(parent)
        self._spacing = DEFAULT_SPACING
        try:
            # Stay a normal child widget (no separate window flags) so we inherit
            # the parent's backing store and avoid full-window black artifacts on some platforms.
            self.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents, True)  # type: ignore
            # Enable true transparency; we'll only paint the grid lines.
            self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground, True)  # type: ignore
        except Exception:
            pass
        self.setObjectName("SpacingGridOverlay")
        try:  # Ensure stylesheet fallback transparency if attribute unsupported
            self.setStyleSheet("background: transparent;")
        except Exception:
            pass

    def sizeHint(self):  # type: ignore[override]
        try:
            if self.parent() and hasattr(self.parent(), "size"):
                return self.parent().size()
        except Exception:
            pass
        return QSize(640, 480)  # type: ignore

    def set_spacing(self, spacing: int):
        spacing = clamp_spacing(spacing)
        if spacing != self._spacing:
            self._spacing = spacing
            try:
                self.update()
            except Exception:
                pass

    def spacing(self) -> int:
        return self._spacing

    def paintEvent(self, event):  # type: ignore
        try:
            painter = QPainter(self)
        except Exception:
            return
        # Do NOT fill the background; rely on translucent background so underlying UI shows through.
        w = self.width()
        h = self.height()
        spacing = self._spacing
        color = None
        try:
            base = self.palette().text().color()
            color = QColor(base)
            color.setAlpha(40)  # slightly more visible
        except Exception:
            try:
                color = QColor(0, 0, 0, 35)  # type: ignore
            except Exception:
                color = None
        if color is None:
            return
        try:
            pen = QPen(color)
            pen.setWidth(1)
            painter.setPen(pen)
            # Vertical lines
            x = 0
            while x <= w:
                painter.drawLine(x, 0, x, h)
                x += spacing
            # Horizontal lines
            y = 0
            while y <= h:
                painter.drawLine(0, y, w, y)
                y += spacing
            painter.end()
        except Exception:
            pass
