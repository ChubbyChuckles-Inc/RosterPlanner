"""Personalization Preview Panel (Milestone 5.10.55)

Allows toggling simulated user preference sets:
 - Reduced Motion
 - High Contrast Theme Variant

Integrates with existing ThemeService (for variant switching) and reduced motion
utility functions provided in gui.design.reduced_motion.

The panel is intentionally minimal and dock-friendly. It emits changes instantly
so other views reacting to theme or motion state update live.
"""

from __future__ import annotations

from typing import Optional
from PyQt6.QtWidgets import (
    QWidget,
    QVBoxLayout,
    QCheckBox,
    QLabel,
    QPushButton,
)

from gui.design.reduced_motion import set_reduced_motion, is_reduced_motion
from gui.services.theme_service import get_theme_service
from gui.services.service_locator import services


class PersonalizationPanel(QWidget):
    """Dockable panel offering user preference simulation toggles."""

    def __init__(self, parent: Optional[QWidget] = None):
        super().__init__(parent)
        self.setObjectName("PersonalizationPanel")
        self._build_ui()
        self._sync_initial_state()

    def _build_ui(self):
        layout = QVBoxLayout(self)
        title = QLabel("Personalization Preview")
        title.setObjectName("viewTitleLabel")
        layout.addWidget(title)
        self.chk_reduced_motion = QCheckBox("Reduced motion (simulate user pref)")
        self.chk_reduced_motion.stateChanged.connect(self._on_reduced_motion_toggled)  # type: ignore
        layout.addWidget(self.chk_reduced_motion)
        self.chk_high_contrast = QCheckBox("High contrast theme")
        self.chk_high_contrast.stateChanged.connect(self._on_high_contrast_toggled)  # type: ignore
        layout.addWidget(self.chk_high_contrast)
        # Reset button convenience
        self.btn_reset = QPushButton("Reset to defaults")
        self.btn_reset.clicked.connect(self._on_reset)  # type: ignore
        layout.addWidget(self.btn_reset)

        self.btn_onboarding = QPushButton("Start onboarding walkthrough")
        self.btn_onboarding.setToolTip("Launch the Ingestion Lab guided tour manually")
        self.btn_onboarding.clicked.connect(self._on_start_onboarding)  # type: ignore
        layout.addWidget(self.btn_onboarding)

        self._status_label = QLabel("")
        self._status_label.setObjectName("personalizationStatusLabel")
        self._status_label.setWordWrap(True)
        self._status_label.setVisible(False)
        layout.addWidget(self._status_label)
        layout.addStretch(1)

    def _sync_initial_state(self):
        self.chk_reduced_motion.setChecked(is_reduced_motion())
        try:
            theme_svc = get_theme_service()
            self.chk_high_contrast.setChecked(theme_svc.manager.variant == "high-contrast")
        except Exception:
            self.chk_high_contrast.setChecked(False)

    # Slots -----------------------------------------------------------
    def _on_reduced_motion_toggled(self):  # pragma: no cover - trivial
        set_reduced_motion(self.chk_reduced_motion.isChecked())

    def _on_high_contrast_toggled(self):  # pragma: no cover - trivial
        try:
            theme_svc = get_theme_service()
        except Exception:
            return
        target = "high-contrast" if self.chk_high_contrast.isChecked() else "default"
        if theme_svc.manager.variant != target:
            theme_svc.set_variant(target)

    def _on_reset(self):  # pragma: no cover - trivial
        self.chk_reduced_motion.setChecked(False)
        self.chk_high_contrast.setChecked(False)
        self._on_reduced_motion_toggled()
        self._on_high_contrast_toggled()

    def _on_start_onboarding(self):  # pragma: no cover - Qt wiring
        panel = services.try_get("ingestion_lab_panel") if services else None
        if panel is None:
            self._update_status("Ingestion Lab panel isn't loaded yet.")
            return
        starter = getattr(panel, "start_onboarding_walkthrough", None)
        if not callable(starter):
            self._update_status("Onboarding walkthrough is unavailable in this build.")
            return
        try:
            started = bool(starter(force_restart=True))
        except Exception as exc:  # pragma: no cover - defensive guard
            self._update_status(f"Couldn't start walkthrough: {exc}")
            return
        if started:
            self._update_status("Onboarding walkthrough launched in the Ingestion Lab.")
        else:
            self._update_status("Open the Ingestion Lab and try again.")

    def _update_status(self, message: str) -> None:
        if not hasattr(self, "_status_label"):
            return
        trimmed = message.strip()
        self._status_label.setText(trimmed)
        self._status_label.setVisible(bool(trimmed))


__all__ = ["PersonalizationPanel"]
