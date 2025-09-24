"""ChromeDialog: frameless dialog with custom title bar and edge resizing.

Provides a lightweight, reusable top-level dialog frame that matches the
application's custom chrome styling without duplicating main-window features
like minimize/maximize or an app icon. Includes:
 - Draggable title bar
 - Close button (X)
 - Edge + corner resizing (configurable margin)
 - Content host widget with layout accessor for child classes

Usage:
    class MyDialog(ChromeDialog):
        def __init__(self, parent=None):
            super().__init__(parent, title="Example")
            lay = self.content_layout()
            lay.addWidget(QLabel("Hello"))

Rationale: The previous approach attempted to retrofit existing QDialog
instances post-construction, which led to geometry/layout edge cases. This
class makes the chrome explicit and stable from the outset.
"""

from __future__ import annotations
from typing import Optional

from PyQt6.QtCore import Qt, QPoint, QEvent, QRect, QObject
from PyQt6.QtWidgets import (
    QDialog,
    QWidget,
    QVBoxLayout,
    QHBoxLayout,
    QLabel,
    QToolButton,
)
from PyQt6.QtGui import QMouseEvent, QCursor

__all__ = ["ChromeDialog"]


class _FramelessResizer(QObject):
    """Utility installed as event filter to enable edge resize on frameless widgets.

    Inherits QObject so installEventFilter accepts it (fixes runtime TypeError).
    """

    def __init__(self, target: QWidget, margin: int = 6):
        super().__init__(target)
        self._t = target
        self._margin = margin
        self._pressed = False
        self._edges = (False, False, False, False)  # left, top, right, bottom
        self._origin_geom: Optional[QRect] = None
        self._origin_pos: Optional[QPoint] = None

    def eventFilter(self, _obj, ev):  # type: ignore
        # Lifetime guard – during shutdown underlying C++ QWidget may already be gone
        try:
            if self._t is None or not self._t.isVisible():
                return False
        except RuntimeError:  # underlying C++ deleted
            return False
        if ev.type() == QEvent.Type.MouseMove:
            pos = self._t.mapFromGlobal(QCursor.pos())
            if not self._pressed:
                l = pos.x() <= self._margin
                t = pos.y() <= self._margin
                r = pos.x() >= self._t.width() - self._margin
                b = pos.y() >= self._t.height() - self._margin
                cursor = None
                if (l and t) or (r and b):
                    cursor = Qt.CursorShape.SizeFDiagCursor
                elif (r and t) or (l and b):
                    cursor = Qt.CursorShape.SizeBDiagCursor
                elif l or r:
                    cursor = Qt.CursorShape.SizeHorCursor
                elif t or b:
                    cursor = Qt.CursorShape.SizeVerCursor
                if cursor:
                    try:
                        self._t.setCursor(cursor)
                    except Exception:
                        pass
                else:
                    try:
                        self._t.unsetCursor()
                    except Exception:
                        pass
                self._edges = (l, t, r, b)
            else:
                if self._origin_geom and self._origin_pos:
                    delta = pos - self._origin_pos
                    g = QRect(self._origin_geom)
                    l, t, r, b = self._edges
                    if l:
                        g.setLeft(g.left() + delta.x())
                    if t:
                        g.setTop(g.top() + delta.y())
                    if r:
                        g.setRight(g.right() + delta.x())
                    if b:
                        g.setBottom(g.bottom() + delta.y())
                    minw = max(self._t.minimumWidth(), 200 if isinstance(self._t, QDialog) else 100)
                    minh = max(self._t.minimumHeight(), 120 if isinstance(self._t, QDialog) else 80)
                    if g.width() < minw:
                        g.setWidth(minw)
                    if g.height() < minh:
                        g.setHeight(minh)
                    self._t.setGeometry(g)
        elif ev.type() == QEvent.Type.MouseButtonPress:
            if ev.button() == Qt.MouseButton.LeftButton and any(self._edges):
                self._pressed = True
                self._origin_geom = self._t.geometry()
                self._origin_pos = self._t.mapFromGlobal(QCursor.pos())
        elif ev.type() == QEvent.Type.MouseButtonRelease:
            if ev.button() == Qt.MouseButton.LeftButton:
                self._pressed = False
        return False


class ChromeDialog(QDialog):
    def __init__(self, parent=None, title: str = "", resize_margin: int = 6):
        super().__init__(parent, flags=Qt.WindowType.FramelessWindowHint | Qt.WindowType.Dialog)
        self.setObjectName("ChromeDialog")
        if title:
            self.setWindowTitle(title)
        self.setAttribute(Qt.WidgetAttribute.WA_DeleteOnClose, True)
        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.setSpacing(0)
        # Title Bar
        self._title_bar = QWidget(self)
        self._title_bar.setObjectName("chromeTitleBar")
        tb = QHBoxLayout(self._title_bar)
        tb.setContentsMargins(12, 4, 8, 4)
        tb.setSpacing(8)
        self._title_label = QLabel(title or "")
        self._title_label.setObjectName("chromeTitleLabel")
        try:
            self._title_label.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents, True)
        except Exception:
            pass
        tb.addWidget(self._title_label, 1)
        self._btn_close = QToolButton()
        self._btn_close.setObjectName("chromeBtnClose")
        self._btn_close.setText("✕")
        self._btn_close.setToolTip("Close")
        try:
            self._btn_close.setAccessibleName("Close dialog")
        except Exception:
            pass
        self._btn_close.clicked.connect(self.close)  # type: ignore
        tb.addWidget(self._btn_close)
        outer.addWidget(self._title_bar, 0)
        # Content
        self._content = QWidget(self)
        self._content.setObjectName("chromeContentHost")
        self._content_layout = QVBoxLayout(self._content)
        # Unified interior spacing for all ChromeDialogs
        self._content_layout.setContentsMargins(12, 10, 12, 12)
        self._content_layout.setSpacing(8)
        outer.addWidget(self._content, 1)
        # Dragging logic
        self._drag_pos: QPoint | None = None
        # Resizer
        self._resizer = _FramelessResizer(self, margin=resize_margin)
        self.installEventFilter(self._resizer)
        # Track title changes
        try:
            self.windowTitleChanged.connect(self._title_label.setText)  # type: ignore
        except Exception:
            pass

    # API ----------------------------------------------------------
    def content_widget(self) -> QWidget:
        return self._content

    def content_layout(self) -> QVBoxLayout:
        return self._content_layout

    # Drag events --------------------------------------------------
    def mousePressEvent(self, e: QMouseEvent):  # type: ignore[override]
        if e.button() == Qt.MouseButton.LeftButton and self._in_title_bar(e.position().toPoint()):
            self._drag_pos = e.globalPosition().toPoint() - self.frameGeometry().topLeft()
        super().mousePressEvent(e)

    def mouseMoveEvent(self, e: QMouseEvent):  # type: ignore[override]
        if self._drag_pos is not None and e.buttons() & Qt.MouseButton.LeftButton:
            self.move(e.globalPosition().toPoint() - self._drag_pos)
            e.accept()
            return
        super().mouseMoveEvent(e)

    def mouseReleaseEvent(self, e: QMouseEvent):  # type: ignore[override]
        self._drag_pos = None
        super().mouseReleaseEvent(e)

    def closeEvent(self, e):  # type: ignore[override]
        # Proactively detach resizer filter to avoid late events on shutdown
        try:
            if self._resizer:
                self.removeEventFilter(self._resizer)
        except Exception:
            pass
        super().closeEvent(e)

    # Helpers ------------------------------------------------------
    def _in_title_bar(self, pt: QPoint) -> bool:
        return 0 <= pt.y() <= self._title_bar.height()
