"""Prompt assist integration for the ingestion lab panel."""

from __future__ import annotations

import json

try:  # pragma: no cover
    from gui.ingestion.prompt_rule_assist import generate_rule_draft, ruleset_to_mapping  # type: ignore
except Exception:  # pragma: no cover
    generate_rule_draft = None  # type: ignore
    ruleset_to_mapping = None  # type: ignore

try:  # pragma: no cover
    from gui.components.chrome_dialog import ChromeDialog
except Exception:  # pragma: no cover
    ChromeDialog = None  # type: ignore

if ChromeDialog is not None:  # pragma: no cover - UI helpers
    from PyQt6.QtWidgets import (
        QDialog,
        QHBoxLayout,
        QLabel,
        QLineEdit,
        QPushButton,
        QVBoxLayout,
    )
    from PyQt6.QtCore import Qt

    PROMPT_ASSIST_MESSAGE = (
        "Describe what to extract (e.g. 'Extract player names and their live rating'):"
    )

    class PromptAssistDialog(ChromeDialog):
        """Chrome-styled prompt input dialog to match other ingestion lab tools."""

        def __init__(self, parent=None):
            super().__init__(parent, title="Prompt Assist")
            try:
                self.setAttribute(Qt.WidgetAttribute.WA_DeleteOnClose, False)
            except Exception:
                pass
            self._result_text = ""
            lay = self.content_layout() if hasattr(self, "content_layout") else QVBoxLayout(self)

            info = QLabel(PROMPT_ASSIST_MESSAGE)
            info.setWordWrap(True)
            lay.addWidget(info)

            self._edit = QLineEdit()
            self._edit.setObjectName("promptAssistInput")
            self._edit.setPlaceholderText("Summarize the extraction goal…")
            lay.addWidget(self._edit)

            buttons = QHBoxLayout()
            buttons.addStretch(1)
            self._ok = QPushButton("OK")
            self._cancel = QPushButton("Cancel")
            buttons.addWidget(self._ok)
            buttons.addWidget(self._cancel)
            lay.addLayout(buttons)

            self._ok.clicked.connect(self._handle_accept)  # type: ignore
            self._cancel.clicked.connect(self.reject)  # type: ignore
            self._edit.returnPressed.connect(self._handle_accept)  # type: ignore

            try:
                self.resize(500, 0)
            except Exception:
                pass

            try:
                self._edit.setFocus()
            except Exception:
                pass

        def _handle_accept(self) -> None:
            self._result_text = self._edit.text()
            self.accept()

        def reject(self) -> None:  # type: ignore[override]
            self._result_text = self._edit.text()
            super().reject()

        def prompt_text(self) -> str:
            return self._result_text or self._edit.text()

    def _prompt_assist_get_text(parent):
        dlg = PromptAssistDialog(parent)
        result = dlg.exec()
        return dlg.prompt_text(), result == int(QDialog.DialogCode.Accepted)

else:  # pragma: no cover - fallback path if chrome dialog unavailable

    PROMPT_ASSIST_MESSAGE = (
        "Describe what to extract (e.g. 'Extract player names and their live rating'):"
    )

    def _prompt_assist_get_text(parent):
        from PyQt6.QtWidgets import QInputDialog

        return QInputDialog.getText(parent, "Prompt Assist", PROMPT_ASSIST_MESSAGE)


__all__ = ["PromptAssistMixin"]


class PromptAssistMixin:
    """Provides the prompt assist button handler."""

    def _on_prompt_assist(self):  # pragma: no cover - UI interaction
        if generate_rule_draft is None:
            self._append_log("Prompt Assist unavailable (module missing)")
            return

        prompt, ok = _prompt_assist_get_text(self)
        if not ok:
            return
        try:
            draft = generate_rule_draft(prompt)
            mapping = ruleset_to_mapping(draft.ruleset) if ruleset_to_mapping else {}
            pretty = json.dumps(mapping, indent=2, ensure_ascii=False)
            self.rule_editor.setPlainText(pretty)
            self._append_log("Prompt Assist generated draft rule set")
            for line in draft.explanation:
                self._append_log("  - " + line)
        except Exception as exc:  # pragma: no cover
            self._append_log(f"Prompt Assist error: {exc}")
