"""Command Palette actions for Ingestion Lab (Milestone 7.10.66).

Adds three user-facing commands:

  ingestion_lab.open
      Focus (or create) the Ingestion Lab dock by publishing the same
      OPEN_INGESTION_LAB event used for auto-open logic.

  ingestion_lab.apply_rules
      Invokes the panel's apply current rule set operation if available.
      Implemented via a best-effort method lookup (``apply_current_rules``)
      to avoid tight coupling. If the method is missing, the command
      silently no-ops.

  ingestion_lab.rollback_previous_rule_version
      Uses the registered ``rule_version_store`` service to retrieve the
      previous version's JSON (if any) and replaces the current draft in
      the panel (method ``load_rules_text``) without auto-applying. This
      allows the user to inspect and then manually apply.

Design Notes:
 - Commands are idempotent; they fail gracefully if panel / services absent.
 - Separation from existing ingest_commands keeps concerns clear.
 - Tests can override services to validate behavior without Qt event loop.
"""

from __future__ import annotations

from typing import Any

from .command_registry import global_command_registry
from .service_locator import services

__all__ = [
    "register_ingestion_lab_commands",
]


def _open_lab() -> None:
    bus = services.try_get("event_bus")
    if bus is not None:  # pragma: no cover - simple publish
        try:
            bus.publish("OPEN_INGESTION_LAB", {"reason": "command"})
        except Exception:
            pass


def _apply_rules() -> None:
    panel = services.try_get("ingestion_lab_panel")
    if not panel:
        return
    # Heuristic method name to avoid importing heavy panel types here
    func = getattr(panel, "apply_current_rules", None)
    if callable(func):  # pragma: no cover - thin wrapper
        try:
            func()
        except Exception:
            pass


def _rollback_previous() -> None:
    store = services.try_get("rule_version_store")
    panel = services.try_get("ingestion_lab_panel")
    if not store or not panel:
        return
    try:
        latest = store.latest() if hasattr(store, "latest") else None
        if not latest:
            return
        prev = store.previous_version(latest.version_num) if hasattr(store, "previous_version") else None
        if not prev:
            return
        raw_json = getattr(prev, "rules_json", None)
        if not isinstance(raw_json, str):
            return
        loader = getattr(panel, "load_rules_text", None)
        if callable(loader):
            loader(raw_json)
    except Exception:  # pragma: no cover - defensive
        pass


def register_ingestion_lab_commands() -> None:
    global_command_registry.register(
        "ingestion_lab.open",
        "Open Ingestion Lab",
        _open_lab,
        description="Show or focus the Ingestion Lab panel",
    )
    global_command_registry.register(
        "ingestion_lab.apply_rules",
        "Apply Current Rule Set",
        _apply_rules,
        description="Apply the currently edited rule set to sandbox",
    )
    global_command_registry.register(
        "ingestion_lab.rollback_previous_rule_version",
        "Revert to Previous Rule Version",
        _rollback_previous,
        description="Load previous rule set version into editor (not auto-applied)",
    )


# Auto-register on import
register_ingestion_lab_commands()