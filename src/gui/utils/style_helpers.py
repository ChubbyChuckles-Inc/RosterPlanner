"""Widget styling utilities.

This module centralizes helpers related to Qt stylesheet behaviour.  It currently
focuses on ensuring widgets that rely on stylesheet-provided backgrounds repaint
correctly by enabling the appropriate Qt attributes.
"""

from __future__ import annotations

from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import QWidget

__all__ = ["ensure_styled_background"]


def ensure_styled_background(widget: QWidget) -> None:
    """Enable attributes needed for reliable stylesheet background repainting.

    When a widget receives a ``background`` declaration via QSS it must opt-in to
    Qt's styled background rendering.  Failing to do so can result in stale
    pixel artifacts ("smeared" text) whenever the widget is resized, moved, or
    reparented.  This helper normalises the two flags required for predictable
    repaint behaviour:

    * :data:`Qt.WidgetAttribute.WA_StyledBackground`
    * :meth:`QWidget.setAutoFillBackground`

    Parameters
    ----------
    widget:
        The target widget.  The helper silently ignores failures which makes it
        safe to call during best-effort theme propagation loops.
    """

    try:
        if not widget.testAttribute(Qt.WidgetAttribute.WA_StyledBackground):
            widget.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
    except Exception:
        # Some specialised widgets (e.g. native views) may not expose the flag.
        pass

    try:
        if not widget.autoFillBackground():
            widget.setAutoFillBackground(True)
    except Exception:
        # Leave widgets that do not support palette based backgrounds untouched.
        pass
