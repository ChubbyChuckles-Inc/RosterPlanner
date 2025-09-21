"""Accessible keyboard-friendly reordering utilities (Milestone 0.45).

This headless module provides logic for implementing a keyboard-only fallback
for drag & drop interactions (e.g., reordering columns, list items, lineup
entries). GUI layers (Qt widgets / models) can wrap these helpers to apply the
resulting order and announce changes via accessible descriptions.

Design goals:
 - Pure logic (no Qt dependency) for easy unit testing.
 - Immutable input -> return new sequence (does not mutate original list).
 - Rich result object containing: new order, focus index to set, a user-facing
   announcement string hook (screen reader friendly), and a flag indicating if
   any change occurred.
 - Guard against out-of-range indices gracefully.

Key Operations Provided:
 - move_up / move_down
 - move_top / move_bottom
 - move_to(index, target_index)
 - move_after(index, after_index)
 - interpret_key(command): helper mapping abstract commands (e.g., 'up',
   'ctrl+home') to operation codes; kept simple for now.

Potential future extensions (not in scope now):
 - Group movement (multiple selection)
 - Undo/redo integration
 - Constraint hooks (disallow moving fixed items)
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable, List, Sequence, Tuple, Callable

__all__ = [
    "ReorderActionResult",
    "ReorderList",
    "move_up",
    "move_down",
    "move_top",
    "move_bottom",
    "move_to",
    "move_after",
    "interpret_key_command",
]


@dataclass(frozen=True)
class ReorderActionResult:
    items: Tuple[str, ...]
    changed: bool
    focus_index: int
    announcement: str


def _validate_index(items: Sequence[str], index: int) -> bool:
    return 0 <= index < len(items)


def _result(
    items: Sequence[str], changed: bool, focus: int, verb: str, original_index: int, new_index: int
) -> ReorderActionResult:
    if not changed:
        announcement = "No change"
    else:
        announcement = f"Moved item from {original_index + 1} to {new_index + 1} ({verb})."
    return ReorderActionResult(tuple(items), changed, focus, announcement)


def _move(items: Sequence[str], src: int, dest: int) -> Tuple[List[str], int, int, bool]:
    if src == dest:
        return list(items), src, dest, False
    lst = list(items)
    if not _validate_index(lst, src) or not _validate_index(lst, dest):
        return list(items), src, src, False
    item = lst.pop(src)
    lst.insert(dest, item)
    # Determine new index of moved item (dest after pop/insert covers both up/down)
    return lst, src, dest, True


def move_up(items: Sequence[str], index: int) -> ReorderActionResult:
    if not _validate_index(items, index) or index == 0:
        return _result(items, False, index, "move-up", index, index)
    new_items, orig, new_pos, changed = _move(items, index, index - 1)
    return _result(new_items, changed, new_pos, "move-up", orig, new_pos)


def move_down(items: Sequence[str], index: int) -> ReorderActionResult:
    if not _validate_index(items, index) or index == len(items) - 1:
        return _result(items, False, index, "move-down", index, index)
    new_items, orig, new_pos, changed = _move(items, index, index + 1)
    return _result(new_items, changed, new_pos, "move-down", orig, new_pos)


def move_top(items: Sequence[str], index: int) -> ReorderActionResult:
    if not _validate_index(items, index) or index == 0:
        return _result(items, False, index, "move-top", index, index)
    new_items, orig, new_pos, changed = _move(items, index, 0)
    return _result(new_items, changed, new_pos, "move-top", orig, new_pos)


def move_bottom(items: Sequence[str], index: int) -> ReorderActionResult:
    if not _validate_index(items, index) or index == len(items) - 1:
        return _result(items, False, index, "move-bottom", index, index)
    new_items, orig, new_pos, changed = _move(items, index, len(items) - 1)
    return _result(new_items, changed, new_pos, "move-bottom", orig, new_pos)


def move_to(items: Sequence[str], index: int, target_index: int) -> ReorderActionResult:
    if not _validate_index(items, index) or not _validate_index(items, target_index):
        return _result(items, False, index, "move-to", index, index)
    new_items, orig, new_pos, changed = _move(items, index, target_index)
    return _result(new_items, changed, new_pos, "move-to", orig, new_pos)


def move_after(items: Sequence[str], index: int, after_index: int) -> ReorderActionResult:
    if not _validate_index(items, index) or not _validate_index(items, after_index):
        return _result(items, False, index, "move-after", index, index)
    # If after_index is same as index or immediately before, it's a no-op
    if after_index == index or after_index == index - 1:
        return _result(items, False, index, "move-after", index, index)
    # Compute destination taking into account removal shift:
    # When moving an item forward (index < after_index), after removal the
    # target position decreases by 1.
    if index < after_index:
        dest = after_index  # after removal, after_index shifts left by 1
    else:
        dest = after_index + 1
    if dest >= len(items):
        dest = len(items) - 1
    new_items, orig, new_pos, changed = _move(items, index, dest)
    return _result(new_items, changed, new_pos, "move-after", orig, new_pos)


# High-level wrapper -----------------------------------------------------


class ReorderList:
    """Mutable façade around immutable operations.

    Maintains an internal tuple sequence; operations update the stored order
    and return the action result. This is convenient for incremental tests or
    an adapter in a ViewModel.
    """

    def __init__(self, items: Iterable[str]):
        self._items: List[str] = list(items)

    @property
    def items(self) -> Tuple[str, ...]:  # expose immutable
        return tuple(self._items)

    def apply(self, result: ReorderActionResult) -> None:
        if result.changed:
            self._items = list(result.items)

    # Convenience bound operations returning result (and mutating when changed)
    def op_move_up(self, index: int) -> ReorderActionResult:
        res = move_up(self._items, index)
        self.apply(res)
        return res

    def op_move_down(self, index: int) -> ReorderActionResult:
        res = move_down(self._items, index)
        self.apply(res)
        return res

    def op_move_top(self, index: int) -> ReorderActionResult:
        res = move_top(self._items, index)
        self.apply(res)
        return res

    def op_move_bottom(self, index: int) -> ReorderActionResult:
        res = move_bottom(self._items, index)
        self.apply(res)
        return res

    def op_move_after(self, index: int, after_index: int) -> ReorderActionResult:
        res = move_after(self._items, index, after_index)
        self.apply(res)
        return res

    def op_move_to(self, index: int, target_index: int) -> ReorderActionResult:
        res = move_to(self._items, index, target_index)
        self.apply(res)
        return res


def interpret_key_command(command: str) -> str:
    """Map an abstract key command to an operation verb.

    This is intentionally coarse; GUI layer decides how to call specific
    movement helpers. Returns one of: up, down, top, bottom.
    Unknown commands return empty string.
    """
    cmd = command.lower()
    if cmd in {"up", "arrowup"}:
        return "up"
    if cmd in {"down", "arrowdown"}:
        return "down"
    if cmd in {"home", "ctrl+home", "top"}:
        return "top"
    if cmd in {"end", "ctrl+end", "bottom"}:
        return "bottom"
    return ""
