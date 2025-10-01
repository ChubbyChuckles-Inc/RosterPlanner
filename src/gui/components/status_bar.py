"""Rich status bar component (Milestone 5.10.59).

Provides token-aligned segmented status indicators:
 - Primary message segment (left aligned)
 - Data freshness pill (last scrape / ingest summary)
 - Mini sparkline segment (placeholder performance / recent event trend)

Design Goals:
 - Non-intrusive: minimal height, respects density & theme tokens
 - Easily extendable: segments exposed via update_* methods
 - Testable: purely QWidget composition without side effects
"""

from __future__ import annotations
from typing import Iterable, List
from PyQt6.QtWidgets import QWidget, QHBoxLayout, QLabel, QSizePolicy
from PyQt6.QtCore import Qt

from gui.components.theme_aware import ThemeAwareMixin
from gui.services.service_locator import services
from gui.utils.style_helpers import ensure_styled_background

__all__ = ["StatusBarWidget"]

_SPARK_CHARS = "▁▂▃▄▅▆▇█"  # 8 steps


def _sparkline(values: Iterable[int]) -> str:
    vals = list(values)
    if not vals:
        return "-"
    vmin = min(vals)
    vmax = max(vals)
    if vmax == vmin:
        # All equal -> middle char
        idx = len(_SPARK_CHARS) // 2
        return _SPARK_CHARS[idx] * min(len(vals), 10)
    span = vmax - vmin
    chars: List[str] = []
    for v in vals[-10:]:  # show last up to 10 samples
        norm = (v - vmin) / span
        ci = int(norm * (len(_SPARK_CHARS) - 1))
        chars.append(_SPARK_CHARS[ci])
    return "".join(chars)


class StatusBarWidget(QWidget, ThemeAwareMixin):
    """Composite status bar with segment labels.

    Methods:
        update_message(text)
        update_freshness(summary)
        update_trend(values)
    """

    def __init__(self):  # pragma: no cover - trivial layout
        super().__init__()
        self.setObjectName("StatusBarRoot")
        ensure_styled_background(self)
        lay = QHBoxLayout(self)
        lay.setContentsMargins(8, 2, 8, 2)
        lay.setSpacing(16)

        self.lbl_message = QLabel("Ready")
        self.lbl_message.setObjectName("StatusMessageLabel")
        self.lbl_message.setAlignment(Qt.AlignmentFlag.AlignVCenter | Qt.AlignmentFlag.AlignLeft)
        self.lbl_message.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Preferred)
        ensure_styled_background(self.lbl_message)
        lay.addWidget(self.lbl_message, 10)

        self.lbl_freshness = QLabel("")
        self.lbl_freshness.setObjectName("StatusFreshnessPill")
        self.lbl_freshness.setAlignment(Qt.AlignmentFlag.AlignCenter)
        ensure_styled_background(self.lbl_freshness)
        lay.addWidget(self.lbl_freshness, 0)

        self.lbl_trend = QLabel("")
        self.lbl_trend.setObjectName("StatusTrendSpark")
        self.lbl_trend.setAlignment(Qt.AlignmentFlag.AlignCenter)
        ensure_styled_background(self.lbl_trend)
        lay.addWidget(self.lbl_trend, 0)

        # Diagnostics (warn/error) badges – hidden by default
        self.lbl_warn = QLabel("")
        self.lbl_warn.setObjectName("StatusWarnBadge")
        self.lbl_warn.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.lbl_warn.setVisible(False)
        ensure_styled_background(self.lbl_warn)
        lay.addWidget(self.lbl_warn, 0)

        self.lbl_error = QLabel("")
        self.lbl_error.setObjectName("StatusErrorBadge")
        self.lbl_error.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.lbl_error.setVisible(False)
        ensure_styled_background(self.lbl_error)
        lay.addWidget(self.lbl_error, 0)

        self._apply_theme(None)
        try:
            theme = services.try_get("theme_service")
            if theme:
                self.on_theme_changed(theme, [])
        except Exception:
            pass

    # Public API --------------------------------------------------
    def update_message(self, text: str) -> None:
        self.lbl_message.setText(text)

    def update_freshness(self, summary: str | None) -> None:
        self.lbl_freshness.setText(summary or "")
        self.lbl_freshness.setVisible(bool(summary))

    def update_trend(self, values: Iterable[int] | None) -> None:
        if not values:
            self.lbl_trend.setText("")
            self.lbl_trend.setVisible(False)
            return
        self.lbl_trend.setText(_sparkline(values))
        self.lbl_trend.setVisible(True)

    def update_diagnostics(self, warn_count: int, error_count: int) -> None:
        """Show/hide warning & error badges based on counts."""
        has_warn = warn_count > 0
        has_error = error_count > 0
        if has_warn:
            self.lbl_warn.setText(f"⚠ {warn_count}")
        self.lbl_warn.setVisible(has_warn)
        if has_error:
            self.lbl_error.setText(f"⛔ {error_count}")
        self.lbl_error.setVisible(has_error)
        # Force a minimal layout update so visibility flags propagate in headless test env
        self.lbl_warn.updateGeometry()
        self.lbl_error.updateGeometry()

    # Styling -----------------------------------------------------
    def _apply_theme(self, theme):  # pragma: no cover - visual
        colors = theme.colors() if hasattr(theme, "colors") else {}
        bg = colors.get("statusbar.background", colors.get("background.secondary", "#1F2732"))
        border = colors.get("statusbar.border", colors.get("border.medium", "#233040"))
        text = colors.get("text.primary", "#FFFFFF")
        muted = colors.get("text.muted", text)
        pill_bg = colors.get("statusbar.pill.background", colors.get("accent.base", "#3D8BFD"))
        pill_fg = colors.get("statusbar.pill.foreground", colors.get("accent.foreground", text))
        warn_bg = colors.get("state.warning.bg", "#FFC107")
        warn_fg = colors.get("state.warning.fg", "#202020")
        error_bg = colors.get("state.error.bg", "#DC3545")
        error_fg = colors.get("state.error.fg", "#FFFFFF")
        spark_font = "'Consolas', 'Courier New', monospace"
        self.setStyleSheet(
            f"""
            QWidget#StatusBarRoot {{ background: {bg}; border-top: 1px solid {border}; }}
            QLabel#StatusMessageLabel {{ font-size: 12px; color: {text}; }}
            QLabel#StatusFreshnessPill {{ padding:2px 6px; border-radius: 8px; background: {pill_bg}; color: {pill_fg}; }}
            QLabel#StatusTrendSpark {{ font-family: {spark_font}; color: {muted}; }}
            QLabel#StatusWarnBadge {{ padding:2px 4px; border-radius:6px; background:{warn_bg}; color:{warn_fg}; font-weight:600; }}
            QLabel#StatusErrorBadge {{ padding:2px 4px; border-radius:6px; background:{error_bg}; color:{error_fg}; font-weight:600; }}
            """
        )

    def on_theme_changed(self, theme, changed_keys):  # pragma: no cover - visual
        self._apply_theme(theme)
