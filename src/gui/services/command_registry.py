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
        """Fuzzy subsequence search over id + title.

        Scoring (lower is better):
         - Non-match => excluded
         - Base score = first match index * 4 + gaps_penalty + length_penalty
         - gaps_penalty = (# of gaps between matched chars) * 2
         - length_penalty = total_hay_length / 200 (small nudge favoring shorter strings)
        Returns up to *limit* best matches. Empty query returns first *limit* commands (stable order by id).
        """
        if not query:
            return sorted(self._commands.values(), key=lambda e: e.command_id)[:limit]
        q = query.lower()
        scored: List[Tuple[float, CommandEntry]] = []
        for entry in self._commands.values():
            hay_original = f"{entry.command_id} {entry.title}"
            hay = hay_original.lower()
            score = _fuzzy_subsequence_score(q, hay)
            if score is not None:
                scored.append((score, entry))
        scored.sort(key=lambda t: (t[0], t[1].command_id))
        return [s[1] for s in scored[:limit]]

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


# --- Fuzzy Scoring Utility (Milestone 2.4.1) ----------------------
def _fuzzy_subsequence_score(pattern: str, text: str) -> Optional[float]:
    """Return a float score for matching pattern as subsequence in text.

    Returns None if not a subsequence. Lower scores are better.
    The algorithm walks *text* trying to match characters of *pattern* in order.
    It tracks the first match index, number of gaps (non-consecutive advances),
    and total text length to produce a composite heuristic score.
    """
    if not pattern:
        return 0.0
    t_len = len(text)
    p_idx = 0
    first_match = -1
    last_match = -1
    gaps = 0
    for i, ch in enumerate(text):
        if ch == pattern[p_idx]:
            if first_match == -1:
                first_match = i
            if last_match != -1 and i - last_match > 1:
                gaps += 1
            last_match = i
            p_idx += 1
            if p_idx == len(pattern):
                break
    if p_idx != len(pattern):
        return None
    # Score components
    gaps_penalty = gaps * 2
    length_penalty = t_len / 200.0
    first_component = first_match * 4
    return first_component + gaps_penalty + length_penalty
