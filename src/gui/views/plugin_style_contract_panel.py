"""Plugin Style Contract Sample Panel (Milestone 5.10.18)."""

from __future__ import annotations

from PyQt6.QtWidgets import (
    QWidget,
    QVBoxLayout,
    QLabel,
    QPushButton,
    QPlainTextEdit,
    QHBoxLayout,
)

from gui.services.service_locator import services
from gui.services.theme_service import ThemeService
from gui.services.plugin_style_contract import StyleContractValidator

__all__ = ["PluginStyleContractPanel"]


class _MockPluginWidget(QLabel):
    def __init__(self) -> None:  # noqa: D401
        super().__init__("Mock Plugin Widget")
        self.setObjectName("mockPluginWidget")
        # Hardcoded style to demonstrate detection
        self.setStyleSheet("QLabel#mockPluginWidget { background:#FF00AA; padding:6px; }")


class PluginStyleContractPanel(QWidget):
    def __init__(self) -> None:  # noqa: D401
        super().__init__()
        self.setObjectName("pluginStyleContractPanel")
        layout = QVBoxLayout(self)
        title = QLabel("Plugin Style Contract Validator")
        title.setObjectName("viewTitleLabel")
        layout.addWidget(title)
        self._mock = _MockPluginWidget()
        layout.addWidget(self._mock)
        btn_row = QHBoxLayout()
        self._refresh_btn = QPushButton("Re-Validate")
        self._refresh_btn.clicked.connect(self._run_validation)  # type: ignore[arg-type]
        btn_row.addWidget(self._refresh_btn)
        btn_row.addStretch(1)
        layout.addLayout(btn_row)
        self._report = QPlainTextEdit()
        self._report.setReadOnly(True)
        layout.addWidget(self._report, 1)
        self._run_validation()

    def _run_validation(self) -> None:
        try:
            theme: ThemeService = services.get_typed("theme_service", ThemeService)
        except Exception:  # pragma: no cover
            self._report.setPlainText("ThemeService unavailable")
            return
        validator = StyleContractValidator.from_theme_mapping(
            theme.colors(), whitelist=["#FFFFFF", "#000000"]
        )
        qss = self._mock.styleSheet() or ""
        report = validator.scan_stylesheet(qss)
        if report.ok:
            text = "All colors conform to theme mapping."
        else:
            lines = [f"Disallowed colors: {report.disallowed}"]
            for issue in report.issues:
                lines.append(f" - {issue.literal} ({issue.reason}) ctx: {issue.context}")
            text = "\n".join(lines)
        self._report.setPlainText(text)
