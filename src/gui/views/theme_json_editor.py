"""Theme JSON Editor Dialog (Milestone 5.10.52)

Provides an in-app editor for authoring or pasting a custom theme override JSON
and previewing it live before applying. Core goals:
 - Live validation (JSON parse + required key presence if provided)
 - Non-destructive preview: apply to ThemeService temporarily until user clicks Apply
 - Rollback on Cancel
 - Minimal dependencies: pure PyQt6 widgets

JSON Schema (subset accepted):
{
  "color": {
     "background": { "primary": "#101010" },
     "accent": { "base": "#3D8BFD" }
  }
}

Only recognized nested groups are flattened (delegates to load_custom_theme logic).
"""

from __future__ import annotations
from typing import Optional

try:  # pragma: no cover - import guard for headless tests
    from PyQt6.QtWidgets import (
        QDialog,
        QVBoxLayout,
        QHBoxLayout,
        QPushButton,
        QPlainTextEdit,
        QLabel,
        QMessageBox,
    )
    from PyQt6.QtCore import Qt
except Exception:  # pragma: no cover
    QDialog = object  # type: ignore

import json

from gui.services.service_locator import services
from gui.services.theme_service import ThemeService, validate_theme_keys
from gui.services.custom_theme import load_custom_theme, CustomThemeError

__all__ = ["ThemeJsonEditorDialog"]


class ThemeJsonEditorDialog(QDialog):  # type: ignore[misc]
    """Dialog for editing and previewing a custom theme JSON mapping."""

    def __init__(self, parent=None):  # pragma: no cover - UI scaffolding
        super().__init__(parent)
        if hasattr(self, "setWindowTitle"):
            self.setWindowTitle("Theme JSON Editor")
        self.setModal(True)
        self.setAttribute(Qt.WidgetAttribute.WA_DeleteOnClose, True)  # type: ignore[attr-defined]
        self._theme: ThemeService = services.get_typed("theme_service", ThemeService)
        self._original = dict(self._theme.colors())  # deep copy snapshot
        layout = QVBoxLayout(self)
        self.info_label = QLabel(
            "Paste or edit JSON. Click Preview to temporarily apply; Apply to persist for session."
        )
        self.info_label.setWordWrap(True)
        layout.addWidget(self.info_label)
        self.editor = QPlainTextEdit(self)
        self.editor.setObjectName("themeJsonEditor")
        self.editor.setPlaceholderText(
            '{\n  "color": {\n    "accent": { "base": "#3D8BFD" }\n  }\n}'
        )
        layout.addWidget(self.editor)
        self.status_label = QLabel("")
        self.status_label.setObjectName("themeJsonStatus")
        layout.addWidget(self.status_label)
        btn_row = QHBoxLayout()
        self.preview_btn = QPushButton("Preview")
        self.apply_btn = QPushButton("Apply")
        self.cancel_btn = QPushButton("Cancel")
        self.preview_btn.clicked.connect(self._on_preview)  # type: ignore[attr-defined]
        self.apply_btn.clicked.connect(self._on_apply)  # type: ignore[attr-defined]
        self.cancel_btn.clicked.connect(self._on_cancel)  # type: ignore[attr-defined]
        btn_row.addWidget(self.preview_btn)
        btn_row.addWidget(self.apply_btn)
        btn_row.addStretch(1)
        btn_row.addWidget(self.cancel_btn)
        layout.addLayout(btn_row)

    # Event handlers -------------------------------------------------
    def _on_preview(self):  # pragma: no cover - direct UI path
        flat = self._parse_editor_json()
        if flat is None:
            return
        changed = self._theme.apply_custom(flat)
        self.status_label.setText(f"Preview applied: {changed} keys changed")

    def _on_apply(self):  # pragma: no cover - direct UI path
        flat = self._parse_editor_json()
        if flat is None:
            return
        changed = self._theme.apply_custom(flat)
        self.status_label.setText(f"Applied: {changed} keys changed (session)")
        self._original = dict(self._theme.colors())  # update baseline

    def _on_cancel(self):  # pragma: no cover - direct UI path
        # Roll back to snapshot
        snapshot = self._original
        rollback = {k: v for k, v in snapshot.items() if k in snapshot}
        self._theme.apply_custom(rollback)
        self.reject()

    # Helpers --------------------------------------------------------
    def _parse_editor_json(self) -> Optional[dict[str, str]]:
        text = self.editor.toPlainText().strip()
        if not text:
            self.status_label.setText("No JSON provided.")
            return None
        try:
            # Use loader for consistent flattening
            data = json.loads(text)
            # Write to a temp file-like path? Instead, mimic load_custom_theme structure directly
            if not isinstance(data, dict):
                raise CustomThemeError("Root must be an object")
            color = data.get("color", {})
            if not isinstance(color, dict):
                raise CustomThemeError("'color' key must map to an object")
            flat: dict[str, str] = {}
            for group, gv in color.items():
                if not isinstance(gv, dict):
                    continue
                for k, v in gv.items():
                    if isinstance(v, str) and v.startswith("#"):
                        flat[f"{group}.{k}"] = v
        except Exception as e:  # noqa: BLE001
            self.status_label.setText(f"Parse error: {e}")
            return None
        missing = validate_theme_keys(flat, required=())  # lenient, no required for partial
        if missing:
            # Not an error; just informational for partial sets
            self.status_label.setText(
                f"Parsed {len(flat)} keys. (Missing core keys not supplied: {len(missing)})"
            )
        else:
            self.status_label.setText(f"Parsed {len(flat)} keys. Ready to preview.")
        return flat
