"""Command Registry Service (Milestone 2.4)

Provides a lightweight in-memory registry for GUI commands exposed to the
Command Palette. Designed for future extension (scoping, permissions,
async execution). Keeps dependencies minimal and test-friendly.

Responsibilities:
 - Register commands with id, title, optional description, callable
 - Prevent duplicate ids (later registrations rejected)
 - Provide fuzzy-ish filtering by simple case-insensitive containment on id or title
 - Execute a command by id with error isolation (returns success flag and optional error)

Future Extensions (roadmap references):
 - 2.4.1 Fuzzy matcher scoring utility (replace naive filter)
 - 2.4.2 Recently executed weighting (maintain recency score)
 - Permissions / enablement predicates
 - Argument passing / parameter schema validation
"""

from __future__ import annotations
from dataclasses import dataclass
from typing import Callable, Dict, List, Optional, Tuple
import traceback

__all__ = ["CommandEntry", "CommandRegistry", "global_command_registry"]


@dataclass(frozen=True)
class CommandEntry:
    command_id: str
    title: str
    description: str
    callback: Callable[[], None]


class CommandRegistry:
    """Central registry for palette-exposed commands.

    Thread-safety: Not currently thread-safe; access from GUI thread only.
    """

    def __init__(self):
        self._commands: Dict[str, CommandEntry] = {}

    # Registration -------------------------------------------------
    def register(
        self, command_id: str, title: str, callback: Callable[[], None], description: str = ""
    ) -> bool:
        """Register a command. Returns False if id already exists."""
        if command_id in self._commands:
            return False
        entry = CommandEntry(
            command_id=command_id, title=title, description=description, callback=callback
        )
        self._commands[command_id] = entry
        return True

    def is_registered(self, command_id: str) -> bool:
        return command_id in self._commands

    # Query / Search -----------------------------------------------
    def list(self) -> List[CommandEntry]:
        return list(self._commands.values())

    def search(self, query: str, limit: int = 25) -> List[CommandEntry]:
        """Naive case-insensitive containment search over id + title.

        Returns up to *limit* matches; if query empty returns all (limited).
        """
        if not query:
            return self.list()[:limit]
        q = query.lower()
        matches: List[Tuple[int, CommandEntry]] = []
        for entry in self._commands.values():
            hay = f"{entry.command_id} {entry.title}".lower()
            idx = hay.find(q)
            if idx != -1:
                # Basic score: earlier match ranks higher; tie-break by id
                matches.append((idx, entry))
        matches.sort(key=lambda t: (t[0], t[1].command_id))
        return [m[1] for m in matches[:limit]]

    # Execution ----------------------------------------------------
    def execute(self, command_id: str) -> Tuple[bool, Optional[str]]:
        entry = self._commands.get(command_id)
        if not entry:
            return False, f"Command not found: {command_id}"
        try:
            entry.callback()
            return True, None
        except Exception as e:  # pragma: no cover (would need failing callback)
            tb = traceback.format_exc()
            return False, f"{e}\n{tb}"


# Global default registry instance (can be replaced or wrapped in DI container)
global_command_registry = CommandRegistry()
