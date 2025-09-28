"""Complexity meter integration for the ingestion lab panel (Milestone 7.10.A14).

This mixin wires the :mod:`gui.ingestion.rule_complexity_meter` heuristics into the
primary panel toolbar. A compact badge reflects the current qualitative
complexity grade (low / moderate / high) and exposes a detailed breakdown via
tooltip. Updates are debounced while the editor text changes to avoid doing
heavy recomputation on every keystroke.
"""

from __future__ import annotations

import json
from typing import Any, Dict, Optional

from PyQt6.QtCore import QTimer, Qt
from PyQt6.QtWidgets import QHBoxLayout, QLabel

from gui.ingestion.rule_complexity_meter import (
    RuleComplexityError,
    RuleComplexityReport,
    compute_rule_complexity,
)

__all__ = ["ComplexityMeterMixin"]


_BADGE_BASE_STYLE = "padding:3px 10px; border-radius:10px; font-weight:600; letter-spacing:0.2px;"
_BADGE_STYLE_MAP = {
    "low": "background-color: rgba(46, 125, 50, 0.85); color: #f8fdf8;",
    "moderate": "background-color: rgba(255, 167, 38, 0.85); color: #1c1300;",
    "high": "background-color: rgba(198, 40, 40, 0.88); color: #fff;",
    "warning": "background-color: rgba(255, 111, 0, 0.65); color: #1a1200;",
    "neutral": "background-color: rgba(128, 128, 128, 0.35); color: #f0f0f0;",
}


class ComplexityMeterMixin:
    """Adds a rule complexity badge and supporting update plumbing."""

    _complexity_badge: QLabel
    _complexity_timer: QTimer
    _last_complexity_report: Optional[RuleComplexityReport]

    def _install_complexity_meter(self, layout: QHBoxLayout) -> None:
        badge = QLabel("Complexity: —")
        badge.setObjectName("ingLabComplexityBadge")
        badge.setAlignment(Qt.AlignmentFlag.AlignCenter)
        badge.setMinimumWidth(150)
        badge.setStyleSheet(_BADGE_BASE_STYLE + _BADGE_STYLE_MAP["neutral"])
        badge.setToolTip(
            "Heuristic complexity score derived from selector depth, transform chain length, and inheritance depth."
        )
        layout.addWidget(badge)
        self._complexity_badge = badge
        timer = QTimer(self)
        timer.setInterval(400)
        timer.setSingleShot(True)
        timer.timeout.connect(self._refresh_complexity_meter)  # type: ignore[attr-defined]
        self._complexity_timer = timer
        self._last_complexity_report = None

    # ------------------------------------------------------------------
    # Public helpers
    def complexity_snapshot(self) -> Dict[str, Any]:
        """Return the last computed complexity report (if available)."""

        if not getattr(self, "_last_complexity_report", None):
            return {}
        return self._last_complexity_report.to_mapping()

    # ------------------------------------------------------------------
    # Event handlers
    def _on_rule_text_changed(self) -> None:  # pragma: no cover - UI event
        super()._on_rule_text_changed()  # type: ignore[misc]
        self._schedule_complexity_refresh()

    def _schedule_complexity_refresh(self, immediate: bool = False) -> None:
        if not hasattr(self, "_complexity_timer"):
            return
        if immediate:
            self._complexity_timer.stop()
            self._refresh_complexity_meter()
        else:
            if self._complexity_timer.isActive():
                self._complexity_timer.stop()
            self._complexity_timer.start()

    # ------------------------------------------------------------------
    # Internal state updates
    def _apply_complexity_state(self, level: str, text: str, tooltip: str) -> None:
        if not hasattr(self, "_complexity_badge"):
            return
        style = _BADGE_STYLE_MAP.get(level, _BADGE_STYLE_MAP["neutral"])
        self._complexity_badge.setStyleSheet(_BADGE_BASE_STYLE + style)
        self._complexity_badge.setText(text)
        self._complexity_badge.setToolTip(tooltip)
        try:
            self._complexity_badge.setProperty("complexityLevel", level)
            self._complexity_badge.style().unpolish(self._complexity_badge)
            self._complexity_badge.style().polish(self._complexity_badge)
        except Exception:  # pragma: no cover - style engine best effort
            pass

    def _refresh_complexity_meter(self) -> None:
        if not hasattr(self, "rule_editor"):
            return
        text = (self.rule_editor.toPlainText() or "").strip()
        if not text:
            self._last_complexity_report = None
            self._apply_complexity_state("neutral", "Complexity: —", "Rule editor is empty.")
            return
        try:
            data = json.loads(text)
        except Exception as exc:
            self._last_complexity_report = None
            self._apply_complexity_state(
                "warning",
                "Complexity: n/a",
                f"Ruleset JSON parse error: {exc}",
            )
            return
        try:
            report = compute_rule_complexity(data)
        except RuleComplexityError as exc:
            self._last_complexity_report = None
            self._apply_complexity_state(
                "warning",
                "Complexity: n/a",
                f"Complexity meter unavailable: {exc}",
            )
            return
        self._last_complexity_report = report
        tooltip_lines = [
            f"Overall score: {report.overall_score:.1f}",
            f"Peak field score: {report.max_score}",
            f"Avg selector depth: {report.selector_avg:.1f}",
            f"Avg transform count: {report.transform_avg:.1f}",
            f"Avg inheritance depth: {report.inheritance_avg:.1f}",
            f"Fields analyzed: {report.field_count}",
            "",
            report.guidance,
        ]
        tooltip = "\n".join(tooltip_lines)
        text_summary = f"Complexity: {report.grade} ({report.overall_score:.1f})"
        self._apply_complexity_state(report.badge or "neutral", text_summary, tooltip)

    # Utility used by programmatic updates (e.g., after replacing editor text)
    def _force_complexity_refresh(self) -> None:
        self._schedule_complexity_refresh(immediate=True)
