"""Inline Error Badge Component (Milestone 5.10.49).

Displays a compact pill / lozenge indicating a severity state (info, warning,
error, critical). Uses accent token colors for background and accessible text
color (text.primary). Critical maps to the strongest error variant with a
slightly higher emphasis.
"""

from __future__ import annotations
from typing import Optional
from PyQt6.QtWidgets import QLabel
from PyQt6.QtCore import Qt

try:  # token access at runtime (soft dependency for tests)
    from gui.design.theme_manager import ThemeManager  # type: ignore
except Exception:  # pragma: no cover
    ThemeManager = None  # type: ignore

__all__ = ["ErrorBadge"]

_SEVERITIES = {"info", "warning", "error", "critical"}


class ErrorBadge(QLabel):  # pragma: no cover - visual; logic tested
    def __init__(self, text: str = "!", severity: str = "error", parent=None):
        super().__init__(text, parent)
        if severity not in _SEVERITIES:
            severity = "error"
        self._severity = severity
        self.setObjectName("errorBadge")
        self.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.setProperty("severity", self._severity)
        self._apply_style()

    def severity(self) -> str:
        return self._severity

    def set_severity(self, severity: str):
        if severity not in _SEVERITIES or severity == self._severity:
            return
        self._severity = severity
        self.setProperty("severity", self._severity)
        self._apply_style()

    # Internal -------------------------------------------------------
    def _resolve_colors(self) -> tuple[str, str]:
        # Fallback static palette if ThemeManager unavailable
        fallback = {
            "info": ("#2a91d8", "#f5f7fa"),
            "warning": ("#f5a524", "#101418"),
            "error": ("#e5484d", "#f5f7fa"),
            "critical": ("#ff5c61", "#ffffff"),
        }
        if ThemeManager is None:
            return fallback[self._severity]
        try:
            tm = ThemeManager.instance()  # type: ignore[attr-defined]
            tokens = tm.tokens  # type: ignore
            bg = (
                tokens.color("accent", "error")
                if self._severity in {"error", "critical"}
                else tokens.color("accent", self._severity)
            )
            if self._severity == "critical":
                # Slightly brighten critical (if possible) by mixing with primaryHover
                try:
                    hover = tokens.color("accent", "primaryHover")
                    bg = hover if hover else bg
                except Exception:
                    pass
            fg = tokens.color("text", "primary")
            return bg, fg
        except Exception:
            return fallback[self._severity]

    def _apply_style(self):
        bg, fg = self._resolve_colors()
        # Minimal inline QSS (could be centralized later)
        self.setStyleSheet(
            f"QLabel#errorBadge[severity='{self._severity}'] {{"
            f"background:{bg};color:{fg};border-radius:10px;padding:0 6px;font-size:11px;min-width:18px;min-height:16px;}}"
        )

    # Convenience for tests
    def palette_tuple(self) -> tuple[str, str]:
        bg, fg = self._resolve_colors()
        return bg.lower(), fg.lower()
