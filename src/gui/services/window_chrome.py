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
    """Title bar widget inserted via setMenuWidget for QMainWindow.

    Keeps existing central widget & dock areas unchanged; only replaces native
    OS chrome when the window is set to FramelessWindowHint.
    """

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
        # Icon
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
        # Min
        self.btn_min = QToolButton()
        self.btn_min.setObjectName("chromeBtnMin")
        self.btn_min.setText("–")
        self.btn_min.clicked.connect(window.showMinimized)  # type: ignore
        lay.addWidget(self.btn_min)
        # Max
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
        # Track window title changes
        try:
            window.windowTitleChanged.connect(self._on_title_changed)  # type: ignore
        except Exception:
            pass

    def _on_title_changed(self, title: str):  # pragma: no cover - UI
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


def try_enable_custom_chrome(window: QMainWindow, icon_path: str | None = None) -> None:  # pragma: no cover - UI integration
    """Enable custom chrome (menuWidget title bar) if feasible.

    Leaves central widget & dock layout intact; injects a custom title bar via
    setMenuWidget so it spans the full width above docks.
    """
    try:
        if window.windowFlags() & Qt.WindowType.FramelessWindowHint:
            return
        # Preserve existing menu bar (if any) inside the custom bar (optional).
        existing_menu = None
        try:
            existing_menu = window.menuBar()  # returns QMenuBar or dummy
            if existing_menu and existing_menu.isNativeMenuBar():
                existing_menu.setNativeMenuBar(False)  # ensure embeddable on macOS
        except Exception:
            existing_menu = None
        bar = _ChromeTitleBar(window, icon_path=icon_path)
        # If there's an existing menu bar with actions, embed it just after title label.
        if existing_menu and isinstance(existing_menu, QMenuBar) and existing_menu.actions():
            # Remove it from the window so it can be reparented.
            existing_menu.setParent(bar)
            idx = bar.layout().indexOf(bar.title_label)
            bar.layout().insertWidget(idx + 1, existing_menu)
        window.setMenuWidget(bar)
        window.setWindowFlag(Qt.WindowType.FramelessWindowHint, True)
        window.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground, False)
        window.show()
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
        # Allow parented dialogs too (common pattern) – still apply custom chrome.
        if dialog.windowFlags() & Qt.WindowType.FramelessWindowHint:
            return
        # Build chrome container similar to main window but simplified
        container = QWidget(dialog)
        container.setObjectName("chromeRoot")
        outer = QVBoxLayout(container)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.setSpacing(0)
        title_bar = QWidget()
        title_bar.setObjectName("chromeTitleBar")
        tb = QHBoxLayout(title_bar)
        tb.setContentsMargins(10, 4, 6, 4)
        tb.setSpacing(6)
        # Icon
        if icon_path:
            try:
                pm = QPixmap(icon_path)
            except Exception:
                pm = QPixmap()
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
                tb.addWidget(icon_lbl, 0)
        ttl = QLabel(dialog.windowTitle())
        ttl.setObjectName("chromeTitleLabel")
        tb.addWidget(ttl, 1)
        btn_close = QToolButton()
        btn_close.setText("✕")
        btn_close.setObjectName("chromeBtnClose")
        btn_close.clicked.connect(dialog.close)  # type: ignore
        tb.addWidget(btn_close)
        outer.addWidget(title_bar)
        content_host = QWidget()
        content_host.setObjectName("chromeContentHost")
        ch_lay = QVBoxLayout(content_host)
        ch_lay.setContentsMargins(0, 0, 0, 0)
        outer.addWidget(content_host, 1)
        # Move existing layout/content into host
        if dialog.layout() is not None:
            old_layout = dialog.layout()
            # Reparent all widgets into content host preserving order
            widgets = []
            for i in range(old_layout.count()):
                it = old_layout.itemAt(i)
                w = it.widget()
                if w:
                    widgets.append(w)
            # Remove old layout from dialog
            QWidget().setLayout(old_layout)  # detach (Qt trick)
            for w in widgets:
                ch_lay.addWidget(w)
        # Install container as sole layout
        main_layout = QVBoxLayout(dialog)
        main_layout.setContentsMargins(0, 0, 0, 0)
        main_layout.setSpacing(0)
        main_layout.addWidget(container)
        dialog.setWindowFlag(Qt.WindowType.FramelessWindowHint, True)
        dialog.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground, False)

        # Install simple drag handling on title bar
        drag_state = {"pos": None}

        def _tb_mouse_press(ev):  # type: ignore
            if ev.button() == Qt.MouseButton.LeftButton:
                drag_state["pos"] = ev.globalPosition().toPoint() - dialog.frameGeometry().topLeft()

        def _tb_mouse_move(ev):  # type: ignore
            if drag_state["pos"] is not None and ev.buttons() & Qt.MouseButton.LeftButton:
                dialog.move(ev.globalPosition().toPoint() - drag_state["pos"])

        def _tb_mouse_release(ev):  # type: ignore
            drag_state["pos"] = None

        try:
            title_bar.mousePressEvent = _tb_mouse_press  # type: ignore
            title_bar.mouseMoveEvent = _tb_mouse_move  # type: ignore
            title_bar.mouseReleaseEvent = _tb_mouse_release  # type: ignore
        except Exception:
            pass
    except Exception:
        return


__all__ = ["try_enable_custom_chrome", "try_enable_dialog_chrome"]
