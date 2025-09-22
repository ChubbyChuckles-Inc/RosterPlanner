"""Navigation Filter Proxy Model (Milestone 4.2)

Provides case-insensitive substring / fuzzy filtering over the navigation
tree (Season -> Division -> Team). Only team nodes are matched for scoring;
division nodes are retained if any descendant team matches.

To keep dependencies minimal we implement a lightweight fuzzy scorer that
reuses existing fuzzy matcher utilities if available; otherwise falls back
to simple case-insensitive substring containment.
"""

from __future__ import annotations

from typing import Optional
from PyQt6.QtCore import QSortFilterProxyModel, QModelIndex, Qt

try:  # Attempt to import existing fuzzy matcher scoring (Milestone 2.4.1)
    from gui.services.fuzzy_matcher import score_match  # type: ignore
except Exception:  # pragma: no cover - fallback path

    def score_match(pattern: str, text: str) -> float:  # type: ignore
        pattern_lower = pattern.lower()
        text_lower = text.lower()
        if pattern_lower in text_lower:
            # Basic heuristic: longer overlap -> higher score
            return len(pattern_lower) / max(len(text_lower), 1)
        return 0.0


class NavigationFilterProxyModel(QSortFilterProxyModel):  # pragma: no cover - tested via unit tests
    def __init__(self):
        super().__init__()
        self._pattern: str = ""
        # We want recursive filtering semantics
        self.setRecursiveFilteringEnabled(True)

    def setFilterPattern(self, pattern: str):
        pattern = pattern.strip()
        if pattern == self._pattern:
            return
        self._pattern = pattern
        self.invalidateFilter()

    # Filtering ----------------------------------------------------
    def filterAcceptsRow(self, source_row: int, source_parent: QModelIndex) -> bool:  # type: ignore[override]
        if not self._pattern:
            return True
        idx = self.sourceModel().index(source_row, 0, source_parent)  # type: ignore
        node = self.sourceModel().data(idx, Qt.ItemDataRole.UserRole)  # type: ignore
        if node is None:
            return True
        # If division or season: accept if any child matches recursively
        if node.kind in ("season", "division"):
            return self._any_descendant_matches(idx)
        if node.kind == "team":
            return self._match_team_label(node.label)
        return True

    def _match_team_label(self, label: str) -> bool:
        if not self._pattern:
            return True
        score = score_match(self._pattern, label)
        return score > 0

    def _any_descendant_matches(self, parent_index: QModelIndex) -> bool:
        rows = self.sourceModel().rowCount(parent_index)  # type: ignore
        for r in range(rows):
            child = self.sourceModel().index(r, 0, parent_index)  # type: ignore
            node = self.sourceModel().data(child, Qt.ItemDataRole.UserRole)  # type: ignore
            if node and node.kind == "team" and self._match_team_label(node.label):
                return True
            # Recurse if division
            if node and node.kind == "division":
                if self._any_descendant_matches(child):
                    return True
        return False


__all__ = ["NavigationFilterProxyModel"]
