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


class StatusBarWidget(QWidget):
    """Composite status bar with segment labels.

    Methods:
        update_message(text)
        update_freshness(summary)
        update_trend(values)
    """

    def __init__(self):  # pragma: no cover - trivial layout
        super().__init__()
        self.setObjectName("StatusBarRoot")
        lay = QHBoxLayout(self)
        lay.setContentsMargins(8, 2, 8, 2)
        lay.setSpacing(16)

        self.lbl_message = QLabel("Ready")
        self.lbl_message.setObjectName("StatusMessageLabel")
        self.lbl_message.setAlignment(Qt.AlignmentFlag.AlignVCenter | Qt.AlignmentFlag.AlignLeft)
        self.lbl_message.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Preferred)
        lay.addWidget(self.lbl_message, 10)

        self.lbl_freshness = QLabel("")
        self.lbl_freshness.setObjectName("StatusFreshnessPill")
        self.lbl_freshness.setAlignment(Qt.AlignmentFlag.AlignCenter)
        lay.addWidget(self.lbl_freshness, 0)

        self.lbl_trend = QLabel("")
        self.lbl_trend.setObjectName("StatusTrendSpark")
        self.lbl_trend.setAlignment(Qt.AlignmentFlag.AlignCenter)
        lay.addWidget(self.lbl_trend, 0)

        # Diagnostics (warn/error) badges – hidden by default
        self.lbl_warn = QLabel("")
        self.lbl_warn.setObjectName("StatusWarnBadge")
        self.lbl_warn.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.lbl_warn.setVisible(False)
        lay.addWidget(self.lbl_warn, 0)

        self.lbl_error = QLabel("")
        self.lbl_error.setObjectName("StatusErrorBadge")
        self.lbl_error.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.lbl_error.setVisible(False)
        lay.addWidget(self.lbl_error, 0)

        self._apply_style()

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
    def _apply_style(self):  # pragma: no cover - visual
        self.setStyleSheet(
            """
            QWidget#StatusBarRoot { background: palette(AlternateBase); border-top: 1px solid palette(Mid); }
            QLabel#StatusMessageLabel { font-size: 12px; color: palette(WindowText); }
            QLabel#StatusFreshnessPill { padding:2px 6px; border-radius: 8px; background: palette(Button); color: palette(ButtonText); }
            QLabel#StatusTrendSpark { font-family: 'Consolas', 'Courier New', monospace; }
            QLabel#StatusWarnBadge { padding:2px 4px; border-radius:6px; background:#FFC107; color:#202020; font-weight:600; }
            QLabel#StatusErrorBadge { padding:2px 4px; border-radius:6px; background:#DC3545; color:#ffffff; font-weight:600; }
            """
        )
