"""Developer color picker overlay (Milestone 5.10.60).

Lightweight full-window overlay that, when visible, tracks mouse movement,
captures the pixel color under the global cursor, and displays the nearest
design token color key for quick inspection / refactoring.

Usage:
    overlay = ColorPickerOverlay(main_window)
    overlay.show()  # toggled via View menu action in MainWindow

Esc hides the overlay. Clicking copies the token key to clipboard.
"""

from __future__ import annotations

try:  # pragma: no cover - Qt import guard
    from PyQt6.QtCore import Qt, QPoint
    from PyQt6.QtGui import QPainter, QColor, QGuiApplication, QFont, QCursor, QKeyEvent
    from PyQt6.QtWidgets import QWidget, QApplication
except Exception:  # pragma: no cover
    Qt = object  # type: ignore
    QPoint = object  # type: ignore
    QPainter = object  # type: ignore
    QColor = object  # type: ignore
    QGuiApplication = object  # type: ignore
    QFont = object  # type: ignore
    QWidget = object  # type: ignore
    QApplication = object  # type: ignore

from gui.design.color_picker_utils import nearest_color_token, hex_to_rgb, rgb_to_hex


class ColorPickerOverlay(QWidget):  # pragma: no cover - interactive GUI, logic indirectly tested
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName("ColorPickerOverlay")
        try:
            self.setMouseTracking(True)
            # Child widget overlay: keep events, no separate window focus issues.
            self.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents, False)
            self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground, True)
            self.setStyleSheet("background: transparent;")
            self.setFocusPolicy(Qt.FocusPolicy.StrongFocus)
        except Exception:
            pass
        self._last_hex: str | None = None
        self._last_token_key: str | None = None
        self._last_dist: int | None = None
        self._cursor_pos = QPoint(0, 0)  # local coords
        # Ensure overlay covers parent client area when shown
        if parent is not None:
            try:
                self.setGeometry(parent.rect())
            except Exception:
                pass
        # Perform an initial sample at current cursor location so HUD is visible immediately.
        try:
            global_pos = QCursor.pos()  # type: ignore
            self._sample_under_cursor(global_pos)
        except Exception:
            pass

    def showEvent(self, event):  # type: ignore
        # Re-sync geometry & initial sample each time overlay is shown.
        try:
            if self.parent() is not None:
                self.setGeometry(self.parent().rect())
        except Exception:
            pass
        try:
            global_pos = QCursor.pos()  # type: ignore
            self._sample_under_cursor(global_pos)
        except Exception:
            pass
        try:
            self.setFocus()
        except Exception:
            pass
        return super().showEvent(event)  # type: ignore

    # --- Core sampling -------------------------------------------------
    def _sample_under_cursor(self, global_pos):
        screen = None
        try:
            if hasattr(self.window(), "windowHandle") and self.window().windowHandle():  # type: ignore[attr-defined]
                screen = self.window().windowHandle().screen()  # type: ignore[attr-defined]
            if screen is None:
                screen = QGuiApplication.primaryScreen()  # type: ignore
        except Exception:
            screen = None
        if screen is None:
            return
        try:
            geo = screen.grabWindow(0, int(global_pos.x()), int(global_pos.y()), 1, 1)
            img = geo.toImage()
            if img.width() > 0 and img.height() > 0:
                col = img.pixelColor(0, 0)
                hex_color = col.name()  # #rrggbb
                key, token_hex, dist = nearest_color_token(hex_color)
                self._last_hex = hex_color
                self._last_token_key = key
                self._last_dist = dist
                # Keep local cursor pos in sync (anchor HUD near pointer)
                try:
                    self._cursor_pos = self.mapFromGlobal(global_pos)
                except Exception:
                    pass
        except Exception:
            pass

    # --- Events --------------------------------------------------------
    def mouseMoveEvent(self, event):  # type: ignore
        # Always derive global position from QCursor to avoid high-DPI offset issues.
        try:
            global_pos = QCursor.pos()  # type: ignore
        except Exception:
            try:
                global_pos = event.globalPosition().toPoint()
            except Exception:
                global_pos = getattr(event, "globalPos", lambda: self._cursor_pos)()
        self._sample_under_cursor(global_pos)
        try:
            self.update()
        except Exception:
            pass

    def keyPressEvent(self, event):  # type: ignore
        try:
            key = event.key()
        except Exception:
            key = None
        if key == getattr(Qt.Key, "Key_Escape", None):
            self._dismiss()
            return
        return super().keyPressEvent(event)  # type: ignore

    def mousePressEvent(self, event):  # type: ignore
        # Copy token key to clipboard (if available) then dismiss
        if self._last_token_key:
            try:
                QApplication.clipboard().setText(self._last_token_key)  # type: ignore
            except Exception:
                pass
        self._dismiss()

    def _dismiss(self):
        try:
            self.hide()
        except Exception:
            pass
        # Uncheck parent action if present
        try:
            parent = self.parent()
            act = getattr(parent, "_act_color_picker", None)
            if act and hasattr(act, "setChecked"):
                act.setChecked(False)
        except Exception:
            pass

    def resizeEvent(self, event):  # type: ignore
        # Ensure overlay always matches parent size
        if self.parent() is not None:
            try:
                self.setGeometry(self.parent().rect())
            except Exception:
                pass
        super().resizeEvent(event)  # type: ignore

    # --- Painting ------------------------------------------------------
    def paintEvent(self, event):  # type: ignore
        try:
            painter = QPainter(self)
        except Exception:
            return
        # NOTE: We intentionally do NOT fill the entire background so underlying UI remains visible.
        w = self.width()
        h = self.height()
        if self._last_hex and self._last_token_key:
            info = f"{self._last_hex}  →  {self._last_token_key}"
            if self._last_dist == 0:
                info += " (exact)"
            # Compute info box position near cursor with safety margins
            x = self._cursor_pos.x() + 16
            y = self._cursor_pos.y() + 16
            # Prevent overflow bottom/right
            metrics_width = 300
            metrics_height = 46
            if x + metrics_width > w - 8:
                x = max(8, w - metrics_width - 8)
            if y + metrics_height > h - 8:
                y = max(8, h - metrics_height - 8)
            # Draw sample color swatch + text
            try:
                swatch_size = 28
                painter.fillRect(x, y, swatch_size, swatch_size, QColor(self._last_hex))
                # Background for text
                painter.fillRect(
                    x + swatch_size + 4,
                    y,
                    metrics_width - swatch_size - 4,
                    swatch_size,
                    QColor(20, 24, 28, 220),
                )
                painter.setPen(QColor("#f5f7fa"))
                font = painter.font()
                font.setPointSize(max(10, font.pointSize()))
                font.setBold(True)
                painter.setFont(font)
                painter.drawText(x + swatch_size + 12, y + 18, info)
                painter.setPen(QColor("#c3ced9"))
                painter.setFont(QFont(font.family(), max(8, font.pointSize() - 2)))
                painter.drawText(
                    x + swatch_size + 12,
                    y + 33,
                    "Click to copy token key • Esc to exit",
                )
            except Exception:
                pass
        else:
            # Draw an instructional HUD near center so user knows overlay is active
            try:
                text = "Color Picker Active – move cursor to sample (Esc to exit)"
                font = painter.font()
                font.setPointSize(max(11, font.pointSize()))
                painter.setFont(font)
                painter.setPen(QColor("#f5f7fa"))
                # Simple shadow for readability
                cx = self.width() // 2
                cy = self.height() // 2
                painter.fillRect(cx - 260, cy - 24, 520, 40, QColor(20, 24, 28, 200))
                painter.drawText(cx - 250, cy + 4, text)
            except Exception:
                pass
        try:
            painter.end()
        except Exception:
            pass
