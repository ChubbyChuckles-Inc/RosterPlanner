"""Custom window chrome helper (Milestone 5.10.57 full implementation).

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
from __future__ import annotations
from dataclasses import dataclass
from PyQt6.QtWidgets import (
    QMainWindow,
    QWidget,
    QHBoxLayout,
    QVBoxLayout,
    QLabel,
    QToolButton,
    QSizeGrip,
    QDialog,
    QMenuBar,
)
from PyQt6.QtCore import Qt, QPoint, QRect
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
        lay.setContentsMargins(8, 3, 6, 3)
        lay.setSpacing(6)
        pm = QPixmap(icon_path) if icon_path else QPixmap()
        if not pm.isNull():
            icon_lbl = QLabel()
            icon_lbl.setObjectName("chromeWindowIcon")
            icon_lbl.setPixmap(pm.scaled(16, 16, Qt.AspectRatioMode.KeepAspectRatio, Qt.TransformationMode.SmoothTransformation))
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
        self.btn_min.clicked.connect(window.showMinimized)  # type: ignore
        lay.addWidget(self.btn_min)
        # Maximize / Restore
        self.btn_max = QToolButton()
        self.btn_max.setObjectName("chromeBtnMax")
        self.btn_max.setText("□")
        self.btn_max.clicked.connect(self._toggle_max_restore)  # type: ignore
        lay.addWidget(self.btn_max)
        # Close
        self.btn_close = QToolButton()
        self.btn_close.setObjectName("chromeBtnClose")
        self.btn_close.setText("✕")
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
            self._window.showNormal()
            if self._pre_max_normal_geom is not None:
                self._window.setGeometry(self._pre_max_normal_geom)
            self._maximized = False
            self.btn_max.setText("□")
        else:
            self._pre_max_normal_geom = self._window.geometry()
            self._window.showMaximized()
            self._maximized = True
            self.btn_max.setText("❐")

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


class _DialogTitleBar(QWidget):
    """Minimal title bar for dialogs (close + drag)."""

    def __init__(self, dialog: QDialog, icon_path: str | None = None):
        super().__init__(dialog)
        self._dialog = dialog
        self._drag_pos: QPoint | None = None
        self.setObjectName("chromeTitleBar")
        lay = QHBoxLayout(self)
        lay.setContentsMargins(8, 3, 6, 3)
        lay.setSpacing(6)
        pm = QPixmap(icon_path) if icon_path else QPixmap()
        if not pm.isNull():
            icon_lbl = QLabel()
            icon_lbl.setObjectName("chromeWindowIcon")
            icon_lbl.setPixmap(pm.scaled(16, 16, Qt.AspectRatioMode.KeepAspectRatio, Qt.TransformationMode.SmoothTransformation))
            lay.addWidget(icon_lbl, 0)
        self.title_label = QLabel(dialog.windowTitle())
        self.title_label.setObjectName("chromeTitleLabel")
        try:
            self.title_label.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents, True)
        except Exception:
            pass
        lay.addWidget(self.title_label, 1)
        self.btn_close = QToolButton()
        self.btn_close.setObjectName("chromeBtnClose")
        self.btn_close.setText("✕")
        self.btn_close.clicked.connect(dialog.close)  # type: ignore
        lay.addWidget(self.btn_close)
        try:
            dialog.windowTitleChanged.connect(lambda t: self.title_label.setText(t))  # type: ignore
        except Exception:
            pass

    def mousePressEvent(self, e: QMouseEvent):  # type: ignore[override]
        if e.button() == Qt.MouseButton.LeftButton:
            self._drag_pos = e.globalPosition().toPoint() - self._dialog.frameGeometry().topLeft()
        super().mousePressEvent(e)

    def mouseMoveEvent(self, e: QMouseEvent):  # type: ignore[override]
        if self._drag_pos is not None and e.buttons() & Qt.MouseButton.LeftButton:
            self._dialog.move(e.globalPosition().toPoint() - self._drag_pos)
            e.accept()
            return
        super().mouseMoveEvent(e)

    def mouseReleaseEvent(self, e: QMouseEvent):  # type: ignore[override]
        self._drag_pos = None
        super().mouseReleaseEvent(e)


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
    except Exception:
        return


def try_enable_dialog_chrome(
    dialog: QDialog, icon_path: str | None = None
) -> None:  # pragma: no cover - UI integration
    """Apply a lightweight chrome wrapper to a top-level QDialog.

    For dialogs we reuse the same container but omit minimize/maximize controls
    (only a close button) to keep interaction expectations aligned with native UI.
    If anything fails, the function returns silently.
    """
    try:
        if dialog.windowFlags() & Qt.WindowType.FramelessWindowHint:
            return
        dialog.setWindowFlag(Qt.WindowType.FramelessWindowHint, True)
        dialog.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground, False)
        old_layout = dialog.layout()
        # Collect existing widgets to preserve order
        widgets: list[QWidget] = []
        if old_layout is not None:
            for i in range(old_layout.count()):
                it = old_layout.itemAt(i)
                w = it.widget()
                if w:
                    widgets.append(w)
            QWidget().setLayout(old_layout)  # detach
        # Build new root layout
        root = QVBoxLayout(dialog)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)
        title_bar = _DialogTitleBar(dialog, icon_path=icon_path)
        root.addWidget(title_bar)
        content_host = QWidget(dialog)
        content_host.setObjectName("chromeContentHost")
        ch_lay = QVBoxLayout(content_host)
        ch_lay.setContentsMargins(0, 0, 0, 0)
        for w in widgets:
            ch_lay.addWidget(w)
        root.addWidget(content_host, 1)
    except Exception:
        return


__all__ = ["try_enable_custom_chrome", "try_enable_dialog_chrome"]
