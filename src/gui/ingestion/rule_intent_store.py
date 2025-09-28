"""Rule Intent Store (Milestone 7.10.A9).

Provides persistence and in-memory accessors for rule intent comments. The
intent metadata is stored separately from the executable rule schema to keep
rule documents concise while preserving author rationale.
"""

from __future__ import annotations

from dataclasses import dataclass, asdict
from typing import Dict, Mapping
import json
import os

__all__ = ["RuleIntent", "RuleIntentStore"]


@dataclass
class RuleIntent:
    """Structured metadata describing the intent for a rule resource."""

    purpose: str = ""
    assumptions: str = ""
    todo: str = ""

    def trimmed(self) -> "RuleIntent":
        """Return a copy with whitespace-trimmed fields."""

        return RuleIntent(
            purpose=self.purpose.strip(),
            assumptions=self.assumptions.strip(),
            todo=self.todo.strip(),
        )

    def is_empty(self) -> bool:
        """Check whether all metadata fields are empty after trimming."""

        trimmed = self.trimmed()
        return not any([trimmed.purpose, trimmed.assumptions, trimmed.todo])

    def to_mapping(self) -> Dict[str, str]:
        """Convert to a serialisable mapping (with trimmed string values)."""

        trimmed = self.trimmed()
        return {
            "purpose": trimmed.purpose,
            "assumptions": trimmed.assumptions,
            "todo": trimmed.todo,
        }

    @staticmethod
    def from_mapping(data: Mapping[str, str] | None) -> "RuleIntent":
        """Create a :class:`RuleIntent` from a plain mapping."""

        if not data:
            return RuleIntent()
        return RuleIntent(
            purpose=str(data.get("purpose", "") or ""),
            assumptions=str(data.get("assumptions", "") or ""),
            todo=str(data.get("todo", "") or ""),
        )


class RuleIntentStore:
    """Manage loading and saving rule intent metadata on disk."""

    def __init__(self, path: str):
        self.path = path
        self._intents: Dict[str, RuleIntent] = {}
        self.load()

    def load(self) -> None:
        """Load intent metadata from disk, tolerating malformed payloads."""

        if not self.path:
            self._intents = {}
            return
        if not os.path.exists(self.path):
            self._intents = {}
            return
        try:
            with open(self.path, "r", encoding="utf-8", errors="ignore") as fh:
                payload = json.load(fh)
        except (json.JSONDecodeError, OSError):
            self._intents = {}
            return
        if not isinstance(payload, dict):
            self._intents = {}
            return
        resources = payload.get("resources", {})
        intents: Dict[str, RuleIntent] = {}
        if isinstance(resources, dict):
            for name, mapping in resources.items():
                intents[str(name)] = RuleIntent.from_mapping(
                    mapping if isinstance(mapping, Mapping) else None
                )
        self._intents = intents

    def save(self) -> None:
        """Persist current metadata to disk using an atomic write strategy."""

        directory = os.path.dirname(self.path)
        if directory and not os.path.exists(directory):
            os.makedirs(directory, exist_ok=True)
        tmp_path = f"{self.path}.tmp"
        data = {"resources": {name: intent.to_mapping() for name, intent in self._intents.items()}}
        with open(tmp_path, "w", encoding="utf-8") as fh:
            json.dump(data, fh, ensure_ascii=False, indent=2)
        os.replace(tmp_path, self.path)

    def get(self, resource: str) -> RuleIntent:
        """Retrieve metadata for a resource (returns empty intent if absent)."""

        return self._intents.get(resource, RuleIntent())

    def set(self, resource: str, intent: RuleIntent) -> None:
        """Set intent metadata for a resource.

        Empty intents are automatically removed instead of persisting blanks.
        """

        trimmed = intent.trimmed()
        if trimmed.is_empty():
            self._intents.pop(resource, None)
        else:
            self._intents[resource] = trimmed

    def remove(self, resource: str) -> None:
        """Remove metadata entry for a resource if present."""

        self._intents.pop(resource, None)

    def resources(self) -> Dict[str, RuleIntent]:
        """Return a shallow copy of the stored intents mapping."""

        return dict(self._intents)

    def to_mapping(self) -> Dict[str, Dict[str, str]]:
        """Expose a serialisable mapping (useful for testing)."""

        return {name: intent.to_mapping() for name, intent in self._intents.items()}
