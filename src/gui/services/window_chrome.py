"""Custom window chrome helper (refactored – dialog retrofit removed).

Provides an optional frameless window with a custom title bar containing:
 - App title label
 - Drag region
 - Minimize / Maximize / Close buttons
 - Double-click maximize toggle

Feature is opt-in via environment variable ``ENABLE_CUSTOM_CHROME=1`` to avoid
disrupting standard OS behaviors if issues arise. Falls back silently if any
platform limitation or error is encountered. Tested minimally on Windows; other
platforms may require additional tweaks (e.g., Linux window manager hints).

Resizing: Basic edge drag resizing implemented via mouse tracking on outer
frame margins (cursor change + geometry adjust). Kept intentionally light; heavy
hit testing logic can be introduced later if necessary.
"""

from __future__ import annotations
from PyQt6.QtWidgets import (
    QMainWindow,
    QWidget,
    QHBoxLayout,
    QVBoxLayout,
    QLabel,
    QToolButton,
    QMenuBar,
)
from PyQt6.QtCore import Qt, QPoint, QRect, QEvent, QObject
from PyQt6.QtGui import QMouseEvent, QCursor, QPixmap

_ACTIVE_ROLE = "--active"  # suffix for state classes (future theming hook)


class _ChromeTitleBar(QWidget):
    """Title bar widget inserted via setMenuWidget for QMainWindow."""

    def __init__(self, window: QMainWindow, icon_path: str | None = None):
        super().__init__(window)
        self._window = window
        self._drag_pos: QPoint | None = None
        self._maximized = False
        self._pre_max_normal_geom: QRect | None = None
        self.setObjectName("chromeTitleBar")
        lay = QHBoxLayout(self)
        lay.setContentsMargins(12, 4, 8, 4)
        lay.setSpacing(8)
        pm = QPixmap(icon_path) if icon_path else QPixmap()
        if not pm.isNull():
            icon_lbl = QLabel()
            icon_lbl.setObjectName("chromeWindowIcon")
            icon_lbl.setPixmap(
                pm.scaled(
                    16,
                    16,
                    Qt.AspectRatioMode.KeepAspectRatio,
                    Qt.TransformationMode.SmoothTransformation,
                )
            )
            lay.addWidget(icon_lbl, 0)
        self.title_label = QLabel(window.windowTitle())
        self.title_label.setObjectName("chromeTitleLabel")
        try:
            self.title_label.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents, True)
        except Exception:
            pass
        lay.addWidget(self.title_label, 1)
        # Minimize
        self.btn_min = QToolButton()
        self.btn_min.setObjectName("chromeBtnMin")
        self.btn_min.setText("–")
        self.btn_min.setToolTip("Minimize")
        try:
            self.btn_min.setAccessibleName("Minimize window")
        except Exception:
            pass
        self.btn_min.clicked.connect(window.showMinimized)  # type: ignore
        lay.addWidget(self.btn_min)
        # Maximize / Restore
        self.btn_max = QToolButton()
        self.btn_max.setObjectName("chromeBtnMax")
        self.btn_max.setText("□")
        self.btn_max.setToolTip("Maximize / Restore")
        try:
            self.btn_max.setAccessibleName("Maximize or restore window")
        except Exception:
            pass
        self.btn_max.clicked.connect(self._toggle_max_restore)  # type: ignore
        lay.addWidget(self.btn_max)
        # Close
        self.btn_close = QToolButton()
        self.btn_close.setObjectName("chromeBtnClose")
        self.btn_close.setText("✕")
        self.btn_close.setToolTip("Close")
        try:
            self.btn_close.setAccessibleName("Close window")
        except Exception:
            pass
        self.btn_close.clicked.connect(window.close)  # type: ignore
        lay.addWidget(self.btn_close)
        try:
            window.windowTitleChanged.connect(self._on_title_changed)  # type: ignore
        except Exception:
            pass

    def _on_title_changed(self, title: str):  # pragma: no cover
        self.title_label.setText(title)

    def _toggle_max_restore(self):
        if self._maximized:
            # Restore
            self._window.showNormal()
            if self._pre_max_normal_geom is not None:
                self._window.setGeometry(self._pre_max_normal_geom)
            self._maximized = False
            self.btn_max.setText("□")  # show maximize glyph
        else:
            # Maximize
            self._pre_max_normal_geom = self._window.geometry()
            self._window.showMaximized()
            self._maximized = True
            self.btn_max.setText("❐")  # show restore glyph

    def mousePressEvent(self, e: QMouseEvent):  # type: ignore[override]
        if e.button() == Qt.MouseButton.LeftButton:
            self._drag_pos = e.globalPosition().toPoint() - self._window.frameGeometry().topLeft()
        super().mousePressEvent(e)

    def mouseMoveEvent(self, e: QMouseEvent):  # type: ignore[override]
        if self._drag_pos is not None and e.buttons() & Qt.MouseButton.LeftButton:
            self._window.move(e.globalPosition().toPoint() - self._drag_pos)
            e.accept()
            return
        super().mouseMoveEvent(e)

    def mouseReleaseEvent(self, e: QMouseEvent):  # type: ignore[override]
        self._drag_pos = None
        super().mouseReleaseEvent(e)

    def mouseDoubleClickEvent(self, e: QMouseEvent):  # type: ignore[override]
        self._toggle_max_restore()
        super().mouseDoubleClickEvent(e)


class _MainWindowResizer(QObject):
    """Edge / corner resize handler for frameless main window."""

    def __init__(self, window: QMainWindow, margin: int = 6):
        super().__init__(window)
        self._w = window
        self._margin = margin
        self._pressed = False
        self._edges = (False, False, False, False)  # left, top, right, bottom
        self._origin_geom: QRect | None = None
        self._origin_pos: QPoint | None = None

    def eventFilter(self, _obj, ev):  # type: ignore
        # Guard against C++ object deletion during shutdown
        try:
            if self._w is None or not self._w.isVisible():
                return False
        except RuntimeError:
            return False
        if self._w.isMaximized():
            return False
        t = ev.type()
        if t == QEvent.Type.MouseMove:
            pos = self._w.mapFromGlobal(QCursor.pos())
            if not self._pressed:
                l = pos.x() <= self._margin
                t_ = pos.y() <= self._margin
                r = pos.x() >= self._w.width() - self._margin
                b = pos.y() >= self._w.height() - self._margin
                cursor = None
                if (l and t_) or (r and b):
                    cursor = Qt.CursorShape.SizeFDiagCursor
                elif (r and t_) or (l and b):
                    cursor = Qt.CursorShape.SizeBDiagCursor
                elif l or r:
                    cursor = Qt.CursorShape.SizeHorCursor
                elif t_ or b:
                    cursor = Qt.CursorShape.SizeVerCursor
                if cursor:
                    self._w.setCursor(cursor)
                else:
                    self._w.unsetCursor()
                self._edges = (l, t_, r, b)
            else:
                if self._origin_geom and self._origin_pos:
                    delta = pos - self._origin_pos
                    g = QRect(self._origin_geom)
                    l, t_, r, b = self._edges
                    if l:
                        g.setLeft(g.left() + delta.x())
                    if t_:
                        g.setTop(g.top() + delta.y())
                    if r:
                        g.setRight(g.right() + delta.x())
                    if b:
                        g.setBottom(g.bottom() + delta.y())
                    minw = max(self._w.minimumWidth(), 640)
                    minh = max(self._w.minimumHeight(), 400)
                    if g.width() < minw:
                        g.setWidth(minw)
                    if g.height() < minh:
                        g.setHeight(minh)
                    self._w.setGeometry(g)
        elif t == QEvent.Type.MouseButtonPress and ev.button() == Qt.MouseButton.LeftButton:
            if any(self._edges):
                self._pressed = True
                self._origin_geom = self._w.geometry()
                self._origin_pos = self._w.mapFromGlobal(QCursor.pos())
        elif t == QEvent.Type.MouseButtonRelease and ev.button() == Qt.MouseButton.LeftButton:
            self._pressed = False
        return False


def try_enable_custom_chrome(
    window: QMainWindow, icon_path: str | None = None
) -> None:  # pragma: no cover - UI integration
    """Enable custom chrome (menuWidget title bar) if feasible.

    Leaves central widget & dock layout intact; injects a custom title bar via
    setMenuWidget so it spans the full width above docks.
    """
    try:
        if window.windowFlags() & Qt.WindowType.FramelessWindowHint:
            return
        window.setWindowFlag(Qt.WindowType.FramelessWindowHint, True)
        window.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground, False)
        existing_menu = None
        try:
            existing_menu = window.menuBar()
            if existing_menu and existing_menu.isNativeMenuBar():
                existing_menu.setNativeMenuBar(False)
        except Exception:
            existing_menu = None
        bar = _ChromeTitleBar(window, icon_path=icon_path)
        if existing_menu and isinstance(existing_menu, QMenuBar) and existing_menu.actions():
            existing_menu.setParent(bar)
            idx = bar.layout().indexOf(bar.title_label)
            bar.layout().insertWidget(idx + 1, existing_menu)
        window.setMenuWidget(bar)
        # Attach edge resize filter once
        try:
            if not hasattr(window, "_mw_resizer"):
                resizer = _MainWindowResizer(window, margin=6)
                window._mw_resizer = resizer  # type: ignore[attr-defined]
                window.installEventFilter(resizer)
        except Exception:
            pass
    except Exception:
        return


__all__ = ["try_enable_custom_chrome"]
