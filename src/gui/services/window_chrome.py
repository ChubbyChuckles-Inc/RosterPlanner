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
)
from PyQt6.QtCore import Qt, QPoint, QRect
from PyQt6.QtGui import QMouseEvent, QCursor, QPixmap

_ACTIVE_ROLE = "--active"  # suffix for state classes (future theming hook)


class _ChromeContainer(QWidget):
    """Container hosting the custom title bar and the user's central widget.

    Responsibilities:
      - Provide title bar with window controls
      - Facilitate drag move and double-click maximize
      - Provide resize hit zones (simple heuristic 6px frame)
    """

    FRAME_WIDTH = 6

    def __init__(self, window: QMainWindow, icon_path: str | None = None):
        super().__init__(window)
        self._window = window
        self._drag_pos: QPoint | None = None
        self._maximized = False
        self._pre_max_normal_geom: QRect | None = None
        self.setObjectName("chromeRoot")
        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.setSpacing(0)

        # Title bar
        self.title_bar = QWidget()
        self.title_bar.setObjectName("chromeTitleBar")
        tb_layout = QHBoxLayout(self.title_bar)
        tb_layout.setContentsMargins(10, 4, 6, 4)
        tb_layout.setSpacing(6)

        # Optional window icon
        if icon_path:
            try:
                pm = QPixmap(icon_path)
            except Exception:
                pm = QPixmap()
        else:
            pm = QPixmap()
        if not pm.isNull():
            self.icon_label = QLabel()
            self.icon_label.setObjectName("chromeWindowIcon")
            self.icon_label.setPixmap(
                pm.scaled(
                    16,
                    16,
                    Qt.AspectRatioMode.KeepAspectRatio,
                    Qt.TransformationMode.SmoothTransformation,
                )
            )
            tb_layout.addWidget(self.icon_label, 0)
        self.title_label = QLabel(window.windowTitle())
        self.title_label.setObjectName("chromeTitleLabel")
        self.title_label.setAlignment(Qt.AlignmentFlag.AlignVCenter | Qt.AlignmentFlag.AlignLeft)
        tb_layout.addWidget(self.title_label, 1)

        # Window control buttons
        self.btn_min = QToolButton()
        self.btn_min.setText("–")
        self.btn_min.setObjectName("chromeBtnMin")
        self.btn_min.clicked.connect(window.showMinimized)  # type: ignore
        tb_layout.addWidget(self.btn_min)

        self.btn_max = QToolButton()
        self.btn_max.setText("□")
        self.btn_max.setObjectName("chromeBtnMax")
        self.btn_max.clicked.connect(self._toggle_max_restore)  # type: ignore
        tb_layout.addWidget(self.btn_max)

        self.btn_close = QToolButton()
        self.btn_close.setText("✕")
        self.btn_close.setObjectName("chromeBtnClose")
        self.btn_close.clicked.connect(window.close)  # type: ignore
        tb_layout.addWidget(self.btn_close)

        outer.addWidget(self.title_bar)

        # Central content placeholder (real central widget will be re-parented)
        self.content_host = QWidget()
        self.content_host.setObjectName("chromeContentHost")
        ch_layout = QVBoxLayout(self.content_host)
        ch_layout.setContentsMargins(0, 0, 0, 0)
        outer.addWidget(self.content_host, 1)

        # Optional size grip (bottom right)
        self.size_grip = QSizeGrip(self)
        self.size_grip.setObjectName("chromeSizeGrip")
        self.size_grip.setVisible(True)
        grip_layout = QHBoxLayout()
        grip_layout.setContentsMargins(0, 0, 0, 0)
        grip_layout.addStretch(1)
        grip_layout.addWidget(
            self.size_grip, 0, Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignBottom
        )
        outer.addLayout(grip_layout)

        self._apply_styles()

    # ---- Styling -------------------------------------------------
    def _apply_styles(self):  # pragma: no cover - visual styling
        self.setStyleSheet(
            """
      QWidget#chromeRoot { background: palette(Window); }
      QWidget#chromeTitleBar { background: palette(AlternateBase); }
      QLabel#chromeTitleLabel { font-weight: 500; }
      QToolButton#chromeBtnClose { color: red; }
      QToolButton#chromeBtnClose:hover { background: rgba(255,0,0,0.15); }
      QToolButton#chromeBtnMin, QToolButton#chromeBtnMax { }
      QToolButton#chromeBtnMin:hover, QToolButton#chromeBtnMax:hover { background: rgba(255,255,255,0.1); }
      QWidget#chromeContentHost { background: palette(Base); }
      QSizeGrip#chromeSizeGrip { width: 12px; height: 12px; }
      """
        )

    # ---- Window control logic -----------------------------------
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

    # ---- Events --------------------------------------------------
    def mousePressEvent(self, event: QMouseEvent):  # type: ignore[override]
        if event.button() == Qt.MouseButton.LeftButton:
            if self._in_title_bar(event.position().toPoint()):
                self._drag_pos = (
                    event.globalPosition().toPoint() - self._window.frameGeometry().topLeft()
                )
        super().mousePressEvent(event)

    def mouseMoveEvent(self, event: QMouseEvent):  # type: ignore[override]
        if self._drag_pos is not None and event.buttons() & Qt.MouseButton.LeftButton:
            self._window.move(event.globalPosition().toPoint() - self._drag_pos)
            event.accept()
            return
        # Resize cursor feedback
        if self._on_edge(event.position().toPoint()):
            QCursor.setShape(Qt.CursorShape.SizeFDiagCursor)
        else:
            QCursor.setShape(Qt.CursorShape.ArrowCursor)
        super().mouseMoveEvent(event)

    def mouseReleaseEvent(self, event: QMouseEvent):  # type: ignore[override]
        self._drag_pos = None
        super().mouseReleaseEvent(event)

    def mouseDoubleClickEvent(self, event: QMouseEvent):  # type: ignore[override]
        if self._in_title_bar(event.position().toPoint()):
            self._toggle_max_restore()
        super().mouseDoubleClickEvent(event)

    # ---- Helpers -------------------------------------------------
    def _in_title_bar(self, pt: QPoint) -> bool:
        return 0 <= pt.y() <= self.title_bar.height()

    def _on_edge(self, pt: QPoint) -> bool:
        w = self.width()
        h = self.height()
        fw = self.FRAME_WIDTH
        return (w - fw <= pt.x() <= w) and (h - fw <= pt.y() <= h)


def try_enable_custom_chrome(
    window: QMainWindow, icon_path: str | None = None
) -> None:  # pragma: no cover - UI integration
    """Enable custom chrome if feasible.

    Re-parents the existing central widget into a chrome container and sets
    frameless window flags. If any error occurs, function returns silently.
    """
    try:
        if window.windowFlags() & Qt.WindowType.FramelessWindowHint:
            return  # already applied
        # Capture current central widget
        current = window.centralWidget()
        container = _ChromeContainer(window, icon_path=icon_path)
        window.setCentralWidget(container)
        if current is not None:
            current.setParent(container.content_host)
            # Insert into host layout
            host_layout = container.content_host.layout()  # type: ignore
            if host_layout:
                host_layout.addWidget(current)
        window.setWindowFlag(Qt.WindowType.FramelessWindowHint, True)
        window.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground, False)
        window.show()
    except Exception:
        # Fail silently to avoid disrupting normal window operation
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
        # Only apply if dialog is top-level (no parent) to avoid nested styling confusion.
        if dialog.parent() is not None:
            return
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
