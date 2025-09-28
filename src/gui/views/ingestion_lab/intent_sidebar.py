"""Intent sidebar helpers for the ingestion lab panel."""

from __future__ import annotations

from typing import Dict

from gui.ingestion.rule_intent_store import RuleIntent

__all__ = ["IntentSidebarMixin"]


class IntentSidebarMixin:
    """Encapsulate interactions with the rule intent sidebar."""

    def _refresh_intent_resources(self) -> None:
        """Refresh sidebar resource list based on current editor content."""

        resources: list[str] = []
        try:
            rule_set = self._parse_ruleset_from_editor()
        except Exception:
            rule_set = None
        self._current_ruleset = rule_set
        if rule_set is not None:
            try:
                resources = sorted(rule_set.resources.keys())
            except Exception:
                resources = []
        self._intent_sidebar.set_resources(resources)
        try:
            self._watchlist_panel.set_ruleset(rule_set)
        except Exception:
            pass
        target = self._intent_current_resource
        if target and target in resources:
            self._intent_sidebar.select_resource(target)
        elif resources:
            self._intent_sidebar.select_resource(resources[0])
        else:
            self._intent_sidebar.clear_fields()

    def _on_intent_save(self, resource: str, payload: Dict) -> None:
        if not resource:
            self._append_log("Intent save skipped: no resource selected")
            return
        intent = RuleIntent(
            purpose=str(payload.get("purpose", "") or ""),
            assumptions=str(payload.get("assumptions", "") or ""),
            todo=str(payload.get("todo", "") or ""),
        )
        trimmed = intent.trimmed()
        self._intent_store.set(resource, intent)
        try:
            self._intent_store.save()
        except Exception as exc:  # pragma: no cover - IO failure
            self._append_log(f"Intent save failed for {resource}: {exc}")
            return
        if trimmed.is_empty():
            self._append_log(f"Intent cleared for {resource}")
            self._intent_sidebar.load_intent(RuleIntent())
        else:
            self._append_log(f"Intent saved for {resource}")
            self._intent_sidebar.load_intent(self._intent_store.get(resource))

    def _on_intent_resource_changed(self, resource: str) -> None:
        self._intent_current_resource = resource or None
        if not resource:
            self._intent_sidebar.clear_fields()
            return
        self._intent_sidebar.load_intent(self._intent_store.get(resource))
