"""Focus Ring Styling (Milestone 2.7)

Applies an accessible, consistent focus ring to interactive widgets.
Strategy:
 - Install a global event filter on the application or a top-level window.
 - On FocusIn/Out, add/remove a dynamic property 'a11yFocused'.
 - Provide a QSS snippet that styles widgets with that property.
 - Keep logic minimal and safe if PyQt is absent.

Focus Ring Design:
 - 2px outline with semi-transparent accent plus a subtle outer glow.
 - Avoid overriding native disabled/hover states.

Limitations:
 - For complex custom widgets, additional adaptation may be required later.
"""

from __future__ import annotations

try:  # pragma: no cover
    from PyQt6.QtCore import QObject, QEvent
    from PyQt6.QtWidgets import QWidget, QApplication
except Exception:  # pragma: no cover
    QObject = object  # type: ignore
    QEvent = object  # type: ignore
    QWidget = object  # type: ignore
    QApplication = object  # type: ignore

__all__ = ["FocusRingManager", "install_focus_ring"]


FOCUS_QSS = """
/* Accessible focus ring styling (Milestone 2.7) */
*[a11yFocused="true"] {
  outline: 2px solid rgba(70,140,255,0.9);
  outline-offset: 1px;
  border-radius: 3px;
}
/* Provide slight glow using box-shadow emulation via border if supported widgets */
QPushButton[a11yFocused="true"], QLineEdit[a11yFocused="true"], QComboBox[a11yFocused="true"] {
  border: 1px solid rgba(70,140,255,0.9);
}
""".strip()


class FocusRingManager(QObject):  # pragma: no cover (most behavior is GUI runtime)
    def __init__(self, parent=None):
        super().__init__(parent)

    def eventFilter(self, obj, event):  # type: ignore[override]
        et = getattr(event, "type", lambda: None)()
        if et == QEvent.Type.FocusIn:  # type: ignore
            self._mark(obj, True)
        elif et == QEvent.Type.FocusOut:  # type: ignore
            self._mark(obj, False)
        return False

    def _mark(self, widget, state: bool):
        if not isinstance(widget, QWidget):  # type: ignore
            return
        try:
            widget.setProperty("a11yFocused", "true" if state else "false")
            # Trigger style refresh
            widget.style().unpolish(widget)
            widget.style().polish(widget)
            widget.update()
        except Exception:
            pass


def install_focus_ring(app_or_window):  # pragma: no cover
    if not isinstance(app_or_window, (QApplication, QWidget)):  # type: ignore
        return None
    mgr = FocusRingManager(app_or_window)
    # Install on application to catch all widgets
    if isinstance(app_or_window, QApplication):  # type: ignore
        app_or_window.installEventFilter(mgr)  # type: ignore
    else:
        app_or_window.installEventFilter(mgr)  # type: ignore
    # Append stylesheet (avoid duplicates naive check)
    try:
        current = app_or_window.styleSheet()
        if "a11yFocused" not in current:
            app_or_window.setStyleSheet(current + ("\n" if current else "") + FOCUS_QSS)
    except Exception:
        pass
    return mgr
