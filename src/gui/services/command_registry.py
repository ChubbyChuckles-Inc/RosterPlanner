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
        # Usage tracking for 2.4.2 recently executed weighting:
        # _last_exec_order stores an incrementing sequence number for each execution.
        # _exec_sequence is the global monotonically increasing counter.
        # _usage_count tracks how many times a command was executed (frequency boost).
        self._last_exec_order: Dict[str, int] = {}
        self._usage_count: Dict[str, int] = {}
        self._exec_sequence: int = 0

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
         - Recency/Frequency adjustments (2.4.2):
             * Recently executed commands receive a negative offset scaling with recency.
               We treat *lower* composite score as better, so we subtract a boost.
               boost_recent = max(0, (RECENCY_WINDOW - age)) * RECENCY_UNIT where
               age = exec_sequence_now - last_exec_order.
             * Frequently executed commands receive a smaller logarithmic boost.
               boost_freq = log2(usage_count + 1) * FREQ_UNIT.
           These boosts are capped so they can't dominate fuzzy relevance entirely.
        Returns up to *limit* best matches. Empty query returns first *limit* commands (stable order by id).
        """
        import math

        q = query.lower()
        ranked: List[Tuple[float, CommandEntry]] = []
        for entry in self._commands.values():
            hay = f"{entry.command_id} {entry.title}".lower()
            base = _fuzzy_subsequence_score(q, hay)
            if base is None:
                continue
            last_order = self._last_exec_order.get(entry.command_id, 0)
            usage = self._usage_count.get(entry.command_id, 0)
            # Composite scoring strategy (Milestone 2.4.2 refinement):
            # Make recency dominant so the most recently executed command rises to top even
            # if another command has slightly better raw fuzzy score. Frequency gives a smaller boost.
            # We subtract boosts because lower score is better.
            composite = base - (last_order * 100.0) - (math.log2(usage + 1) * 5.0)
            ranked.append((composite, entry))
        ranked.sort(key=lambda t: (t[0], t[1].command_id))
        return [r[1] for r in ranked[:limit]]

    # Execution ----------------------------------------------------
    def execute(self, command_id: str) -> Tuple[bool, Optional[str]]:
        entry = self._commands.get(command_id)
        if not entry:
            return False, f"Command not found: {command_id}"
        try:
            entry.callback()
            # Update recency/frequency tracking (2.4.2)
            self._exec_sequence += 1
            self._last_exec_order[command_id] = self._exec_sequence
            self._usage_count[command_id] = self._usage_count.get(command_id, 0) + 1
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
