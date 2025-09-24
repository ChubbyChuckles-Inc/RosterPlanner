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
        QListWidget,
        QListWidgetItem,
        QWidget,
        QGridLayout,
        QColorDialog,
        QScrollArea,
    )
    from PyQt6.QtCore import Qt
except Exception:  # pragma: no cover
    QDialog = object  # type: ignore

import json

from gui.services.service_locator import services
from gui.services.theme_service import ThemeService, validate_theme_keys
from gui.services.custom_theme import load_custom_theme, CustomThemeError
from gui.services.window_chrome import try_enable_dialog_chrome

__all__ = ["ThemeJsonEditorDialog"]


class ThemeJsonEditorDialog(QDialog):  # type: ignore[misc]
    """Dialog for editing and previewing a custom theme JSON mapping."""

    def __init__(self, parent=None):  # pragma: no cover - UI scaffolding
        super().__init__(parent)
        if hasattr(self, "setWindowTitle"):
            self.setWindowTitle("Theme JSON Editor")
        self.setModal(True)
        self.setObjectName("ThemeJsonEditorDialog")
        try:
            try_enable_dialog_chrome(self, icon_path="assets/icons/base/table-tennis.png")
        except Exception:
            pass
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
        # Filesystem theme list + export row
        fs_row = QHBoxLayout()
        self.fs_list = QListWidget()
        self.fs_list.setMaximumHeight(90)
        fs_row.addWidget(QLabel("Available FS Themes:"))
        fs_row.addWidget(self.fs_list, 1)
        self.reload_btn = QPushButton("Reload")
        self.export_btn = QPushButton("Export Current")
        fs_row.addWidget(self.reload_btn)
        fs_row.addWidget(self.export_btn)
        layout.addLayout(fs_row)

        # Dynamic color key editor (scrollable) -------------------------------------------------
        self.key_editor_area = QScrollArea()
        self.key_editor_area.setWidgetResizable(True)
        self._key_container = QWidget()
        self._key_layout = QGridLayout(self._key_container)
        self.key_editor_area.setMinimumHeight(200)
        self.key_editor_area.setWidget(self._key_container)
        layout.addWidget(QLabel("Interactive Color Keys:"))
        layout.addWidget(self.key_editor_area)

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

        # Wire filesystem theme interactions
        try:
            self.reload_btn.clicked.connect(self._reload_fs)  # type: ignore
            self.export_btn.clicked.connect(self._export_current)  # type: ignore
            self.fs_list.itemDoubleClicked.connect(self._apply_fs_item)  # type: ignore
        except Exception:
            pass
        self._reload_fs()
        self._populate_key_editors()
        self._load_current_theme_into_editor()

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

    # Filesystem theme utilities ----------------------------------
    def _reload_fs(self):  # pragma: no cover - UI path
        self.fs_list.clear()
        try:
            names = self._theme.load_filesystem_themes()
            for n in names:
                QListWidgetItem(n, self.fs_list)
        except Exception:
            pass

    def _apply_fs_item(self, item):  # pragma: no cover - UI path
        if not item:
            return
        name = item.text()
        if self._theme.apply_filesystem_theme(name):
            self.status_label.setText(f"Applied filesystem theme: {name}")
            self._original = dict(self._theme.colors())
            self._populate_key_editors()
            self._load_current_theme_into_editor()

    def _export_current(self):  # pragma: no cover - UI path
        out = self._theme.export_current_theme("exported_theme")
        if out:
            self.status_label.setText(f"Exported to {out}")

    # Interactive color key editors -------------------------------
    def _populate_key_editors(self):  # pragma: no cover - UI path
        # Clear layout
        while self._key_layout.count():
            item = self._key_layout.takeAt(0)
            w = item.widget()
            if w:
                w.deleteLater()
        colors = self._theme.colors()
        keys = [
            k
            for k in sorted(colors.keys())
            if any(
                k.startswith(p) for p in ("background.", "surface.", "text.", "accent.", "border.")
            )
        ]
        for row, key in enumerate(keys):
            lbl = QLabel(key)
            btn = QPushButton(colors[key])
            btn.setObjectName(f"colorKeyBtn_{key}")
            btn.clicked.connect(lambda _=False, k=key, b=btn: self._edit_color_key(k, b))  # type: ignore
            self._key_layout.addWidget(lbl, row, 0)
            self._key_layout.addWidget(btn, row, 1)

    def _edit_color_key(self, key: str, btn: QPushButton):  # pragma: no cover - UI path
        try:
            col = QColorDialog.getColor()  # native dialog
            if not col.isValid():
                return
            hexv = col.name().upper()
            self._theme.apply_custom({key: hexv})
            btn.setText(hexv)
            # Update editor JSON view snapshot
            self._load_current_theme_into_editor()
            self.status_label.setText(f"Updated {key} -> {hexv}")
        except Exception:
            pass

    def _load_current_theme_into_editor(self):  # pragma: no cover - UI path
        # Reconstruct grouped JSON
        colors = self._theme.colors()
        grouped: dict[str, dict[str, str]] = {}
        for k, v in colors.items():
            if "." not in k:
                continue
            group, role = k.split(".", 1)
            grouped.setdefault(group, {})[role] = v
        payload = {"color": grouped}
        try:
            self.editor.setPlainText(json.dumps(payload, indent=2))
        except Exception:
            pass
