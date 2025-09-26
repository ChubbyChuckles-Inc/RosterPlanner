"""Lightweight Preferences dialog exposing Command Palette resize settings."""
from __future__ import annotations

try:
    from PyQt6.QtWidgets import (
        QWidget, QVBoxLayout, QCheckBox, QLabel, QComboBox, QSpinBox, QPushButton
    )
    from PyQt6.QtCore import Qt
except Exception:  # pragma: no cover
    QWidget = object  # type: ignore

from gui.components.chrome_dialog import ChromeDialog

class PreferencesDialog(ChromeDialog):  # type: ignore[misc]
    def __init__(self, parent=None):  # pragma: no cover minimal GUI
        super().__init__(parent, title="Preferences")
        lay = self.content_layout()
        try:
            from gui.services.settings_service import SettingsService  # type: ignore
        except Exception:  # pragma: no cover
            SettingsService = None  # type: ignore
        # Command Palette Section
        lay.addWidget(QLabel("Command Palette"))
        self.chk_auto = QCheckBox("Enable Auto-Resize & Animation")
        if SettingsService:
            self.chk_auto.setChecked(SettingsService.instance.command_palette_auto_resize)
        lay.addWidget(self.chk_auto)
        # Duration
        row_dur = QWidget()
        row_lay = QVBoxLayout(row_dur)
        row_lay.setContentsMargins(0,0,0,0)
        self.spin_duration = QSpinBox()
        self.spin_duration.setRange(20, 1000)
        self.spin_duration.setSingleStep(10)
        self.spin_duration.setPrefix("Duration ms: ")
        if SettingsService:
            val = getattr(SettingsService.instance, 'command_palette_anim_duration_ms', 140)
            self.spin_duration.setValue(val if isinstance(val, int) else 140)
        row_lay.addWidget(self.spin_duration)
        lay.addWidget(row_dur)
        # Easing
        self.combo_ease = QComboBox()
        self.combo_ease.addItems(["OutCubic","Linear","InCubic","InOutQuad","ElasticOut"])
        if SettingsService:
            cur = getattr(SettingsService.instance, 'command_palette_anim_easing', 'OutCubic')
            idx = self.combo_ease.findText(str(cur), Qt.MatchFlag.MatchFixedString)  # type: ignore
            if idx >=0:
                self.combo_ease.setCurrentIndex(idx)
        lay.addWidget(self.combo_ease)
        # Apply button
        btn_apply = QPushButton("Apply")
        lay.addWidget(btn_apply)
        btn_apply.clicked.connect(self._apply)  # type: ignore
        self.setFixedWidth(380)

    def _apply(self):  # pragma: no cover straightforward
        try:
            from gui.services.settings_service import SettingsService  # type: ignore
            SettingsService.instance.command_palette_auto_resize = self.chk_auto.isChecked()
            # Store duration/easing as dynamic attributes (not part of dataclass schema yet)
            setattr(SettingsService.instance, 'command_palette_anim_duration_ms', int(self.spin_duration.value()))
            setattr(SettingsService.instance, 'command_palette_anim_easing', self.combo_ease.currentText())
        except Exception:
            pass
        self.accept()

__all__ = ["PreferencesDialog"]
