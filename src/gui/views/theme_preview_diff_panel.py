"""Live Theme Preview Diff Panel (Milestone 5.10.34).

Allows developers to preview diffs for a candidate theme variant or accent
color before applying it. This panel does *not* mutate the global theme;
it uses a simulation ViewModel. Future enhancements could add an "Apply"
button that executes the mutation through ThemeService.
"""

from __future__ import annotations

from PyQt6.QtWidgets import (
    QWidget,
    QVBoxLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QComboBox,
    QPlainTextEdit,
    QHBoxLayout,
)

from gui.services.service_locator import services
from gui.services.theme_service import ThemeService
from gui.viewmodels.theme_preview_diff_viewmodel import (
    ThemePreviewDiffViewModel,
)

__all__ = ["ThemePreviewDiffPanel"]


class ThemePreviewDiffPanel(QWidget):  # pragma: no cover - QWidget wiring
    def __init__(self) -> None:  # noqa: D401
        super().__init__()
        self.setObjectName("themePreviewDiffPanel")
        layout = QVBoxLayout(self)
        title = QLabel("Theme Preview Diff")
        title.setObjectName("viewTitleLabel")
        layout.addWidget(title)
        # Controls row -------------------------------------------------
        row = QHBoxLayout()
        self.variant_combo = QComboBox()
        self.variant_combo.setEditable(False)
        self.accent_input = QLineEdit()
        self.accent_input.setPlaceholderText("#RRGGBB")
        self.sim_variant_btn = QPushButton("Preview Variant")
        self.sim_accent_btn = QPushButton("Preview Accent")
        for w in (
            QLabel("Variant:"),
            self.variant_combo,
            QLabel("Accent:"),
            self.accent_input,
            self.sim_variant_btn,
            self.sim_accent_btn,
        ):
            row.addWidget(w)
        row.addStretch(1)
        layout.addLayout(row)
        # Results ------------------------------------------------------
        self.result = QPlainTextEdit()
        self.result.setReadOnly(True)
        layout.addWidget(self.result, 1)
        self._populate_variants()
        self._capture_baseline()
        self.sim_variant_btn.clicked.connect(self._on_sim_variant)  # type: ignore[arg-type]
        self.sim_accent_btn.clicked.connect(self._on_sim_accent)  # type: ignore[arg-type]

    def _theme_service(self) -> ThemeService:
        return services.get_typed("theme_service", ThemeService)

    def _populate_variants(self) -> None:
        try:
            svc = self._theme_service()
            variants = svc.available_variants()
        except Exception:
            variants = ["default", "high-contrast", "brand-neutral"]
        self.variant_combo.clear()
        for v in variants:
            self.variant_combo.addItem(v)

    def _capture_baseline(self) -> None:
        try:
            svc = self._theme_service()
            self._vm = ThemePreviewDiffViewModel.capture(svc)
        except Exception:
            self._vm = ThemePreviewDiffViewModel(baseline={})

    def _on_sim_variant(self) -> None:
        variant = self.variant_combo.currentText().strip()
        if not variant:
            return
        entries = self._vm.simulate_variant(variant)
        self._display(entries, f"Variant: {variant}")

    def _on_sim_accent(self) -> None:
        accent = self.accent_input.text().strip()
        if not accent or len(accent) != 7 or not accent.startswith("#"):
            self.result.setPlainText("Enter accent in format #RRGGBB")
            return
        entries = self._vm.simulate_accent(accent)
        self._display(entries, f"Accent: {accent}")

    def _display(self, entries, header: str) -> None:
        if not entries:
            self.result.setPlainText(f"{header} -> No changes from baseline")
            return
        lines = [header, f"Changed keys: {len(entries)}", ""]
        for k, old, new in entries[:400]:  # cap output
            lines.append(f"{k}: {old} -> {new}")
        if len(entries) > 400:
            lines.append(f"...({len(entries) - 400} more)")
        self.result.setPlainText("\n".join(lines))
