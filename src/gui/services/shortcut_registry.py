"""Shortcut Registry Service (Milestone 2.5)

Maintains a centralized mapping of logical shortcut ids to their key sequences
and human-readable descriptions. Enables:
 - Listing all shortcuts for cheat sheet dialogs
 - Detecting conflicts (future 2.5.1) by checking duplicate key sequences
 - Programmatic registration for dynamic features / plugins

Design Notes:
 - Keep dependency surface minimal (pure Python; Qt integration occurs where shortcuts created)
 - Key sequences stored as plain strings (Qt-compatible, e.g. 'Ctrl+P', 'Ctrl+Shift+O')
 - Duplicate id registration rejected; duplicate sequence allowed for now (will be flagged in 2.5.1)
"""

from __future__ import annotations
from dataclasses import dataclass
from typing import Dict, List, Optional, Tuple

__all__ = ["ShortcutEntry", "ShortcutRegistry", "global_shortcut_registry"]


@dataclass(frozen=True)
class ShortcutEntry:
    shortcut_id: str
    sequence: str
    description: str
    category: str = "General"


class ShortcutRegistry:
    def __init__(self) -> None:
        self._entries: Dict[str, ShortcutEntry] = {}

    def register(
        self, shortcut_id: str, sequence: str, description: str, category: str = "General"
    ) -> bool:
        """Register a shortcut. Returns False if id already exists.

        No validation of sequence format is performed here to keep this logic decoupled
        from Qt specifics; Qt will validate when creating QShortcut/QAction bindings.
        """
        if shortcut_id in self._entries:
            return False
        self._entries[shortcut_id] = ShortcutEntry(shortcut_id, sequence, description, category)
        return True

    def get(self, shortcut_id: str) -> Optional[ShortcutEntry]:
        return self._entries.get(shortcut_id)

    def list(self) -> List[ShortcutEntry]:
        return list(self._entries.values())

    def by_category(self) -> Dict[str, List[ShortcutEntry]]:
        buckets: Dict[str, List[ShortcutEntry]] = {}
        for e in self._entries.values():
            buckets.setdefault(e.category, []).append(e)
        for lst in buckets.values():
            lst.sort(key=lambda x: x.sequence)
        return buckets

    # Conflict Detection (Milestone 2.5.1) -------------------------
    def find_conflicts(self) -> Dict[str, List[ShortcutEntry]]:
        """Return mapping of key sequence -> entries when more than one shortcut shares it.

        Sequences compared in a case-insensitive manner (normalized to upper).
        """
        seq_map: Dict[str, List[ShortcutEntry]] = {}
        for e in self._entries.values():
            norm = e.sequence.upper()
            seq_map.setdefault(norm, []).append(e)
        return {k: v for k, v in seq_map.items() if len(v) > 1}


# Global instance
global_shortcut_registry = ShortcutRegistry()
