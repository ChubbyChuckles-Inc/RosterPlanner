"""Prompt assist integration for the ingestion lab panel."""

from __future__ import annotations

import json

try:  # pragma: no cover
    from gui.ingestion.prompt_rule_assist import generate_rule_draft, ruleset_to_mapping  # type: ignore
except Exception:  # pragma: no cover
    generate_rule_draft = None  # type: ignore
    ruleset_to_mapping = None  # type: ignore

__all__ = ["PromptAssistMixin"]


class PromptAssistMixin:
    """Provides the prompt assist button handler."""

    def _on_prompt_assist(self):  # pragma: no cover - UI interaction
        if generate_rule_draft is None:
            self._append_log("Prompt Assist unavailable (module missing)")
            return
        from PyQt6.QtWidgets import QInputDialog

        prompt, ok = QInputDialog.getText(
            self,
            "Prompt Assist",
            "Describe what to extract (e.g. 'Extract player names and their live rating'):",
        )
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
