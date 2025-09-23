"""Plugin Visual Sandbox Panel (Milestone 5.10.43).

Provides a lightweight environment to validate that plugin-provided widgets
adhere to the token-only styling contract (no hardcoded colors). For now this
panel renders a small mock plugin widget list and runs the same regex-based
scan used conceptually by the drift detector. Future iterations can accept
real plugin module references once plugin loading (Milestone 12) lands.
"""

from __future__ import annotations
from typing import List, Tuple

try:  # pragma: no cover - GUI specifics not unit tested here
    from PyQt6.QtWidgets import (
        QWidget,
        QVBoxLayout,
        QLabel,
        QPushButton,
        QListWidget,
        QListWidgetItem,
    )
except Exception:  # pragma: no cover
    QWidget = object  # type: ignore
    QVBoxLayout = object  # type: ignore
    QLabel = object  # type: ignore
    QPushButton = object  # type: ignore
    QListWidget = object  # type: ignore
    QListWidgetItem = object  # type: ignore

import re

HEX_RE = re.compile(r"#[0-9a-fA-F]{3}(?:[0-9a-fA-F]{3})\b")

TRANSITIONAL_ALLOWED = {
    "#FF5722",
    "#FF8800",
    "#202020",
    "#3D8BFD",
    "#ffffff",
    "#202830",
    "#FF00AA",
    "#000000",
    "#FFFFFF",
}


def scan_widget_stylesheet(widget) -> List[Tuple[str, str]]:
    """Return list of (literal, context) for disallowed hex colors in widget stylesheets.

    Currently only inspects the widget's own styleSheet() text. In later phases
    this can traverse children or accept a provided QSS snippet.
    """
    offenders: List[Tuple[str, str]] = []
    try:
        ss = widget.styleSheet() or ""
    except Exception:  # pragma: no cover
        return offenders
    for m in HEX_RE.finditer(ss):
        lit = m.group(0)
        if lit in TRANSITIONAL_ALLOWED:
            continue
        if lit.lower() in ("#000", "#fff"):
            continue
        offenders.append((lit, "root"))
    return offenders


class PluginVisualSandboxPanel(QWidget):  # pragma: no cover - structural
    def __init__(self):
        super().__init__()
        self.setObjectName("PluginVisualSandboxPanel")
        layout = QVBoxLayout()
        self.setLayout(layout)
        title = QLabel("Plugin Visual Sandbox (Token Usage Validation)")
        layout.addWidget(title)
        desc = QLabel(
            "This panel hosts sample plugin-like widgets and runs a scan to ensure no hardcoded color literals are used outside the design token system."
        )
        desc.setWordWrap(True)
        layout.addWidget(desc)
        self._list = QListWidget()
        layout.addWidget(self._list)
        # Populate mock plugin widgets (names only for now)
        for name in ("Sample Plugin Card", "Analytics Widget", "Experimental Badge"):
            QListWidgetItem(name, self._list)
        self._status_label = QLabel("Scan not yet run")
        layout.addWidget(self._status_label)
        run_btn = QPushButton("Run Style Scan")
        run_btn.clicked.connect(self._run_scan)  # type: ignore
        layout.addWidget(run_btn)

    def _run_scan(self):  # pragma: no cover - UI path
        offenders = scan_widget_stylesheet(self)
        if offenders:
            msg = f"Style issues: {len(offenders)} hardcoded colors detected"
        else:
            msg = "All clear: no disallowed hardcoded colors"
        try:
            self._status_label.setText(msg)
        except Exception:
            pass


__all__ = ["PluginVisualSandboxPanel", "scan_widget_stylesheet"]
