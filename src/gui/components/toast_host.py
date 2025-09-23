"""Toast / notification presentation layer (Milestone 5.10.11).

Provides a lightweight widget host (`ToastHost`) that stacks transient
notification widgets ("toasts") in a vertical column. A companion
`NotificationManager` coordinates creation, stacking order, and dismissal
timers based on the semantic `NotificationStyle` registry defined in
`gui.design.notifications`.

Design goals:
 - Pure PyQt6 (no external deps) / minimal logic
 - Style data (severity, timeout, color role) sourced from style registry
 - Theme-aware: actual colors resolved via `ThemeService.colors()` mapping
 - Testable: timers can be disabled; exposes current notification IDs
 - Future extension: animations (fade / slide) and accessibility announcements

Usage:
    host = ToastHost(parent_window)
    manager = NotificationManager(host, theme_service)
    manager.show_notification('info', 'Data loaded successfully')

When attached to a top-level window, callers should position the host in an
overlay fashion (e.g., by placing it in a layout corner widget or using
`setParent(window)` with `raise_()` + manual geometry). For now, tests exercise
only logical stacking & dismissal (no animations).
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, List, Optional, TYPE_CHECKING
from PyQt6.QtWidgets import (
    QWidget,
    QVBoxLayout,
    QLabel,
    QHBoxLayout,
    QPushButton,
)
from PyQt6.QtCore import Qt, QTimer, QPropertyAnimation, QEasingCurve, QRect, QPoint

from gui.design.notifications import get_notification_style, list_notification_styles

if TYPE_CHECKING:  # pragma: no cover
    from gui.services.theme_service import ThemeService
else:  # runtime placeholder

    class ThemeService:  # type: ignore
        pass


__all__ = ["ToastHost", "NotificationManager", "NotificationData"]


@dataclass
class NotificationData:
    """Runtime notification instance state."""

    notif_id: int
    style_id: str
    message: str
    timeout_ms: int
    widget: QWidget
    timer: Optional[QTimer]
    remaining_ms: int = 0
    paused: bool = False


class ToastItem(QWidget):
    """Toast widget wrapper that notifies manager about hover state."""

    def __init__(self, manager: "NotificationManager", parent: Optional[QWidget] = None):
        super().__init__(parent)
        self._manager = manager

    def enterEvent(self, event):  # type: ignore[override]
        self._manager._on_toast_hover(self)
        return super().enterEvent(event)

    def leaveEvent(self, event):  # type: ignore[override]
        self._manager._on_toast_unhover(self)
        return super().leaveEvent(event)


class ToastHost(QWidget):
    """Container widget stacking toast notifications vertically.

    The host itself uses a transparent background; each toast is an individual
    child widget styled through QSS. The host adds stretch at the end so new
    items appear at the top (common toast convention) while still allowing
    potential reversed ordering later if desired.
    """

    def __init__(self, parent: Optional[QWidget] = None):
        super().__init__(parent)
        self.setObjectName("toastHost")
        self.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(8)
        # A stretch at the end ensures new inserts at index 0 appear visually first
        layout.addStretch(1)

    def add_toast_widget(self, widget: QWidget, insert_index: int) -> None:
        layout = self.layout()
        # Insert before the final stretch (which is last item)
        stretch_pos = layout.count() - 1
        layout.insertWidget(min(insert_index, stretch_pos), widget)

    def remove_toast_widget(self, widget: QWidget) -> None:
        layout = self.layout()
        layout.removeWidget(widget)
        widget.setParent(None)

    def toast_widgets(self) -> List[QWidget]:  # pragma: no cover - trivial
        out: List[QWidget] = []
        for i in range(self.layout().count() - 1):  # skip final stretch
            item = self.layout().itemAt(i)
            if item and item.widget():
                out.append(item.widget())
        return out


class NotificationManager:
    """Coordinator for displaying toast notifications within a `ToastHost`.

    Responsibilities:
     - Translate style ids -> NotificationStyle definitions
     - Create/destroy toast widgets
     - Maintain stacking order (ascending stacking_priority)
     - Manage auto-dismiss timers (unless disabled for tests)
    """

    _next_id: int = 1

    def __init__(
        self,
        host: ToastHost,
        theme_service: Optional[ThemeService] = None,
        *,
        disable_timers: bool = False,
        enable_animations: bool = True,
    ) -> None:
        self._host = host
        self._theme = theme_service
        self._disable_timers = disable_timers
        self._enable_animations = enable_animations
        self._notifications: Dict[int, NotificationData] = {}
        # Pre-cache style priority for ordering decisions
        self._style_priority: Dict[str, int] = {
            s.id: s.stacking_priority for s in list_notification_styles()
        }
        self._stagger_base_ms = 40  # cascade per item

    # Public API --------------------------------------------------
    def show_notification(
        self,
        style_id: str,
        message: str,
        *,
        timeout_override_ms: Optional[int] = None,
    ) -> int:
        style = get_notification_style(style_id) or get_notification_style("info")
        if style is None:  # pragma: no cover - defensive
            raise ValueError(f"Unknown notification style: {style_id}")
        timeout_ms = (
            timeout_override_ms if timeout_override_ms is not None else style.default_timeout_ms
        )
        widget = self._build_toast_widget(style.id, message)
        notif_id = self._allocate_id()
        widget.setProperty("style_id", style.id)
        widget.setProperty("severity", style.severity)
        data = NotificationData(
            notif_id=notif_id,
            style_id=style.id,
            message=message,
            timeout_ms=timeout_ms,
            widget=widget,
            timer=None,
        )
        self._insert_notification_widget(data)
        if timeout_ms > 0 and not self._disable_timers:
            timer = QTimer(widget)
            timer.setSingleShot(True)
            timer.setInterval(timeout_ms)
            timer.timeout.connect(lambda nid=notif_id: self.dismiss(nid))  # type: ignore
            data.timer = timer
            timer.start()
            data.remaining_ms = timeout_ms
        self._notifications[notif_id] = data
        return notif_id

    def dismiss(self, notif_id: int) -> bool:
        data = self._notifications.pop(notif_id, None)
        if not data:
            return False
        if data.timer and data.timer.isActive():
            data.timer.stop()
        try:
            self._host.remove_toast_widget(data.widget)
        except Exception:
            pass
        return True

    def active_ids(self) -> List[int]:
        return sorted(self._notifications.keys())

    def clear(self) -> None:
        for nid in list(self._notifications.keys()):
            self.dismiss(nid)

    # Internals ---------------------------------------------------
    def _allocate_id(self) -> int:
        nid = NotificationManager._next_id
        NotificationManager._next_id += 1
        return nid

    def _build_toast_widget(self, style_id: str, message: str) -> QWidget:
        w = ToastItem(self, self._host)
        w.setObjectName("toastWidget")
        w.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
        hl = QHBoxLayout(w)
        hl.setContentsMargins(12, 8, 12, 8)
        hl.setSpacing(8)
        label = QLabel(message)
        label.setObjectName("toastMessage")
        label.setWordWrap(True)
        hl.addWidget(label)
        close_btn = QPushButton("✕")
        close_btn.setObjectName("toastCloseButton")
        close_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        close_btn.setFixedSize(20, 20)
        close_btn.clicked.connect(lambda _=False, s_id=style_id: self._on_close_clicked(w))  # type: ignore
        hl.addWidget(close_btn, alignment=Qt.AlignmentFlag.AlignTop)
        return w

    def _on_close_clicked(self, widget: QWidget) -> None:
        # Find the notification id by widget
        for nid, data in list(self._notifications.items()):
            if data.widget is widget:
                self.dismiss(nid)
                break

    def _insert_notification_widget(self, data: NotificationData) -> None:
        # Determine insertion index based on stacking priority (lower -> earlier)
        priority = self._style_priority.get(data.style_id, 100)
        existing = list(self._notifications.values())
        index = 0
        for existing_data in sorted(
            existing, key=lambda d: self._style_priority.get(d.style_id, 100)
        ):
            existing_pri = self._style_priority.get(existing_data.style_id, 100)
            if existing_pri <= priority:
                index += 1
        self._host.add_toast_widget(data.widget, index)
        # Apply cascade animation (slide + fade) unless disabled
        if self._enable_animations and not self._disable_timers:
            self._animate_appearance(data.widget, index)

    # Animation helpers -------------------------------------------
    def _animate_appearance(self, widget: QWidget, index: int) -> None:  # pragma: no cover - timing
        try:
            start_geo: QRect = widget.geometry()
            # Start slightly lower and transparent
            offset = QPoint(0, 12)
            widget.setWindowOpacity(0.0)
            widget.move(start_geo.topLeft() + offset)
            dur = 180 + min(index, 5) * 10
            # Fade
            fade = QPropertyAnimation(widget, b"windowOpacity", widget)
            fade.setDuration(dur)
            fade.setStartValue(0.0)
            fade.setEndValue(1.0)
            fade.setEasingCurve(QEasingCurve.Type.OutCubic)
            # Slide
            slide = QPropertyAnimation(widget, b"pos", widget)
            slide.setDuration(dur)
            slide.setStartValue(widget.pos())
            slide.setEndValue(start_geo.topLeft())
            slide.setEasingCurve(QEasingCurve.Type.OutCubic)
            # Stagger start
            delay = index * self._stagger_base_ms
            QTimer.singleShot(delay, fade.start)
            QTimer.singleShot(delay, slide.start)
        except Exception:
            pass

    # Hover pause / resume --------------------------------------
    def _on_toast_hover(self, widget: QWidget) -> None:
        for data in self._notifications.values():
            if data.widget is widget and data.timer and not data.paused:
                remaining = data.timer.remainingTime()
                if remaining > 0:
                    data.remaining_ms = remaining
                    data.paused = True
                    data.timer.stop()
                break

    def _on_toast_unhover(self, widget: QWidget) -> None:
        for nid, data in self._notifications.items():
            if data.widget is widget and data.paused and data.remaining_ms > 0:
                if data.timer is None:
                    t = QTimer(widget)
                    t.setSingleShot(True)
                    t.timeout.connect(lambda nid=nid: self.dismiss(nid))  # type: ignore
                    data.timer = t
                data.timer.setInterval(max(50, data.remaining_ms))
                data.paused = False
                data.timer.start()
                break
