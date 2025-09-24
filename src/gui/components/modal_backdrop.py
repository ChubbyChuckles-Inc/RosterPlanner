"""Modal backdrop helper (Milestone 5.10.66).

Provides a lightweight semi-transparent backdrop widget plus optional subtle
zoom-in animation for a supplied *content* widget (e.g. a dialog container)
when shown. Respects reduced motion preference.

Usage::

    backdrop = ModalBackdrop(parent_window)
    backdrop.show_with_content(dialog_widget)
    # later
    backdrop.dismiss()

Behavior
--------
* Backdrop fills parent geometry; darkens using design token friendly RGBA.
* Content widget is centered inside parent (unless already positioned) and
  temporarily scaled via a transform proxy (implemented as geometry tween).
* When reduced motion is active the content appears instantly without zoom.

Test Strategy
-------------
We abstract timing + effect logic so tests can assert:
* Opacity final value (stored attribute)
* Zoom animation skipped when reduced motion enabled
* Dismiss resets internal references

Limitations
-----------
Scaling uses geometry interpolation (true Qt 6.6+ QTransform animations are
not relied upon to keep compatibility with earlier minor versions or headless
test contexts).
"""

from __future__ import annotations

from typing import Optional

from PyQt6.QtCore import Qt, QPropertyAnimation, QRect, QEasingCurve, pyqtProperty
from PyQt6.QtWidgets import QWidget

try:  # Prefer "src." import to share singleton state with tests using src.*
    from src.gui.design import reduced_motion as _reduced_motion  # type: ignore
except ImportError:  # Fallback for runtime where package exposed without src prefix
    from gui.design import reduced_motion as _reduced_motion  # type: ignore
from gui.design.motion import get_duration_ms, get_easing_curve
from gui.design.loader import load_tokens

__all__ = ["ModalBackdrop"]


class ModalBackdrop(QWidget):
    def __init__(self, parent: QWidget, dark_rgba=(0, 0, 0, 160)):
        super().__init__(parent)
        self.setObjectName("ModalBackdrop")
        self.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents, False)
        self.setAttribute(Qt.WidgetAttribute.WA_NoSystemBackground, True)
        self.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
        self._content: Optional[QWidget] = None
        self._dark_rgba = dark_rgba
        self._opacity = 0.0
        self._fade_anim: Optional[QPropertyAnimation] = None
        self._zoom_anim: Optional[QPropertyAnimation] = None
        self.hide()

    # Painting ----------------------------------------------------------------
    def paintEvent(self, event):  # type: ignore[override]
        from PyQt6.QtGui import QPainter, QColor

        p = QPainter(self)
        r, g, b, a = self._dark_rgba
        final_a = int(a * self._opacity)
        p.fillRect(self.rect(), QColor(r, g, b, final_a))

    # Public API --------------------------------------------------------------
    def show_with_content(self, content: QWidget):
        self._content = content
        parent = self.parentWidget()
        if parent is None:
            raise RuntimeError("Backdrop requires a parent widget")
        self.setGeometry(0, 0, parent.width(), parent.height())
        self.raise_()
        content.setParent(self)
        # Center content if not yet positioned
        if content.geometry().x() == 0 and content.geometry().y() == 0:
            cw, ch = content.sizeHint().width(), content.sizeHint().height()
            cx = max(0, (self.width() - cw) // 2)
            cy = max(0, (self.height() - ch) // 2)
            content.setGeometry(cx, cy, cw, ch)
        content.show()
        self._start_animations()
        self.show()

    def dismiss(self):
        if self._content:
            self._content.hide()
            self._content.setParent(None)
        self._content = None
        self.hide()
        self._opacity = 0.0
        self.update()

    def is_active(self) -> bool:
        return self.isVisible() and self._content is not None

    # Internal ----------------------------------------------------------------
    def _start_animations(self):
        tokens = load_tokens()
        # Use an existing motion duration token; earlier milestones define 'base'.
        try:
            duration = get_duration_ms(tokens, "base")
        except Exception:  # fallback defensive
            duration = 200
        reduced = _reduced_motion.is_reduced_motion()
        actual_fade = _reduced_motion.adjust_duration(duration, minimum_ms=0 if reduced else 0)
        # Fade animation (backdrop opacity)
        if reduced:
            self._opacity = 1.0
        else:
            self._fade_anim = QPropertyAnimation(self, b"backdropOpacity")
            self._fade_anim.setStartValue(0.0)
            self._fade_anim.setEndValue(1.0)
            self._fade_anim.setDuration(actual_fade)
            self._fade_anim.setEasingCurve(QEasingCurve.Type.InOutCubic)
            self._fade_anim.start()
        # Zoom animation (geometry scale via tween) if content set
        if self._content:
            content = self._content
            if reduced:
                self._zoom_anim = None
            else:
                start_rect = QRect(content.geometry())
                dw = int(start_rect.width() * 0.04)
                dh = int(start_rect.height() * 0.04)
                start_rect.adjust(dw, dh, -dw, -dh)
                self._zoom_anim = QPropertyAnimation(content, b"geometry")
                self._zoom_anim.setStartValue(start_rect)
                self._zoom_anim.setEndValue(content.geometry())
                self._zoom_anim.setDuration(actual_fade)
                self._zoom_anim.setEasingCurve(QEasingCurve.Type.OutCubic)
                self._zoom_anim.start()
        self._opacity = 1.0 if reduced else 0.0  # will reach 1.0 at end of fade

    # Property for animation driver -------------------------------------------
    def backdropOpacity(self):  # getter for QPropertyAnimation
        return self._opacity

    def setBackdropOpacity(self, value):  # setter for animation
        self._opacity = float(value)
        self.update()

    backdropOpacity = pyqtProperty(float, fget=backdropOpacity, fset=setBackdropOpacity)  # type: ignore
