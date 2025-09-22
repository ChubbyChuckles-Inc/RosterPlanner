"""Navigation Filter Proxy Model (Milestone 4.2)

Provides case-insensitive substring / fuzzy filtering over the navigation
tree (Season -> Division -> Team). Only team nodes are matched for scoring;
division nodes are retained if any descendant team matches.

To keep dependencies minimal we implement a lightweight fuzzy scorer that
reuses existing fuzzy matcher utilities if available; otherwise falls back
to simple case-insensitive substring containment.
"""

from __future__ import annotations

from typing import Optional, List, Tuple
from PyQt6.QtCore import (
    QSortFilterProxyModel,
    QModelIndex,
    Qt,
    QTimer,
    QObject,
    pyqtSignal,
    QThread,
)


class _IndexBuildWorker(QObject):  # pragma: no cover - lightweight thread helper
    built = pyqtSignal(list)

    def __init__(self, snapshot: List[Tuple[str, object]]):  # (label, node)
        super().__init__()
        self._snapshot = snapshot

    def run(self):  # Slot executed in thread
        # Precompute lowercase labels (and maybe tokenization later)
        processed = [(label, label.lower()) for label, _ in self._snapshot]
        self.built.emit(processed)


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
        # Debounce timer (250ms)
        self._debounce = QTimer()
        self._debounce.setInterval(250)
        self._debounce.setSingleShot(True)
        self._debounce.timeout.connect(self._apply_pending_pattern)  # type: ignore
        self._pending_pattern: Optional[str] = None

        # Background indexing (labels cache)
        self._index_thread: Optional[QThread] = None
        self._label_index: List[Tuple[str, str]] | None = None  # (original, lower)
        self._index_ready = False

        # Chip-based filters (Milestone 4.3)
        # Accept empty sets meaning: no restriction
        self._division_types: set[str] = set()  # e.g., {"Erwachsene", "Jugend"}
        self._levels: set[str] = set()  # e.g., {"Bezirksliga", "Stadtliga", "Stadtklasse"}
        self._active_only: bool = False

    def __del__(self):  # pragma: no cover - defensive cleanup
        try:
            if self._index_thread and self._index_thread.isRunning():
                self._index_thread.quit()
                self._index_thread.wait(100)
        except Exception:
            pass

    # Chip Filter Setters -----------------------------------------
    def setDivisionTypes(self, types: set[str]):
        if types == self._division_types:
            return
        self._division_types = set(types)
        self.invalidateFilter()

    def setLevels(self, levels: set[str]):
        if levels == self._levels:
            return
        self._levels = set(levels)
        self.invalidateFilter()

    def setActiveOnly(self, active: bool):
        if active == self._active_only:
            return
        self._active_only = active
        self.invalidateFilter()

    # Public API ---------------------------------------------------
    def scheduleFilterPattern(self, pattern: str):
        """Debounced filter setter (Milestone 4.2.1)."""
        self._pending_pattern = pattern
        self._debounce.start()

    def setFilterPattern(self, pattern: str):
        pattern = pattern.strip()
        if pattern == self._pattern:
            return
        self._pattern = pattern
        self.invalidateFilter()

    # Internal -----------------------------------------------------
    def _apply_pending_pattern(self):
        if self._pending_pattern is None:
            return
        self.setFilterPattern(self._pending_pattern)
        self._pending_pattern = None

    def _ensure_index(self):
        if self._index_ready or self.sourceModel() is None:
            return
        # Snapshot team nodes
        snapshot: List[Tuple[str, object]] = []
        root = QModelIndex()
        rows = self.sourceModel().rowCount(root)  # type: ignore
        for r in range(rows):
            div_idx = self.sourceModel().index(r, 0, root)  # type: ignore
            snapshot.extend(self._collect_team_nodes(div_idx))
        # Launch thread
        self._index_thread = QThread()
        worker = _IndexBuildWorker(snapshot)
        worker.moveToThread(self._index_thread)
        self._index_thread.started.connect(worker.run)  # type: ignore
        worker.built.connect(self._on_index_built)  # type: ignore
        # Teardown
        worker.built.connect(worker.deleteLater)  # type: ignore
        worker.built.connect(self._index_thread.quit)  # type: ignore
        self._index_thread.finished.connect(self._index_thread.deleteLater)  # type: ignore
        self._index_thread.start()

    def _on_index_built(self, processed: List[Tuple[str, str]]):
        self._label_index = processed
        self._index_ready = True
        # Re-run current filter with index in place
        self.invalidateFilter()

    def _collect_team_nodes(self, division_idx: QModelIndex) -> List[Tuple[str, object]]:
        out: List[Tuple[str, object]] = []
        # Ensure division children loaded (virtualization) by probing rowCount
        _ = self.sourceModel().rowCount(division_idx)  # type: ignore
        rows = self.sourceModel().rowCount(division_idx)  # type: ignore
        for r in range(rows):
            team_idx = self.sourceModel().index(r, 0, division_idx)  # type: ignore
            node = self.sourceModel().data(team_idx, Qt.ItemDataRole.UserRole)  # type: ignore
            if node and getattr(node, "kind", None) == "team":
                out.append((node.label, node))
        return out

    # Filtering ----------------------------------------------------
    def filterAcceptsRow(self, source_row: int, source_parent: QModelIndex) -> bool:  # type: ignore[override]
        # Basic early accept if no text pattern & no chip filters
        if (
            not self._pattern
            and not self._division_types
            and not self._levels
            and not self._active_only
        ):
            return True
        # Kick off index build if a text pattern is involved
        if self._pattern:
            self._ensure_index()
        idx = self.sourceModel().index(source_row, 0, source_parent)  # type: ignore
        node = self.sourceModel().data(idx, Qt.ItemDataRole.UserRole)  # type: ignore
        if node is None:
            return True
        if node.kind == "season":
            # Season node acts as container. If we have any restrictive filters (pattern or active_only)
            # we only keep it if some descendant team passes; otherwise always keep.
            if self._pattern or self._active_only or self._division_types or self._levels:
                return self._any_descendant_matches(idx)
            return True
        if node.kind == "division":
            # If division fails chip meta filters -> entire subtree excluded.
            if not self._division_meta_pass(node.label):
                return False
            # If we have a text pattern or active-only requirement, only keep divisions
            # that have at least one matching descendant team.
            if self._pattern or self._active_only:
                return self._any_descendant_matches(idx)
            return True
        if node.kind == "team":
            # Team must satisfy chip filters (evaluated on its division parent) + pattern
            parent_div = node.parent.label if node.parent else ""
            if not self._division_meta_pass(parent_div):
                return False
            if self._pattern and not self._match_team_label(node.label):
                return False
            if self._active_only:
                # Placeholder active flag logic: treat teams containing inactive marker as inactive.
                # Real implementation would consult a repository / state.
                if "(inactive)" in node.label.lower():
                    return False
            return True
        return True

    # Chip filter helpers -----------------------------------------
    def _division_meta_pass(self, division_label: str) -> bool:
        """Check division label against chip filters.

        Conventions (simplistic heuristics for now):
        - Division label contains "Jugend" -> Jugend, else Erwachsene.
        - Level classification based on substring in label.
        """
        # Division type
        if self._division_types:
            div_type = "Jugend" if "Jugend" in division_label else "Erwachsene"
            if div_type not in self._division_types:
                return False
        if self._levels:
            level = None
            if "Bezirksliga" in division_label:
                level = "Bezirksliga"
            elif "Stadtliga" in division_label:
                level = "Stadtliga"
            elif "Stadtklasse" in division_label:
                level = "Stadtklasse"
            if level and level not in self._levels:
                return False
            if level is None and self._levels:
                return False
        return True

    def _match_team_label(self, label: str) -> bool:
        if not self._pattern:
            return True
        score = score_match(self._pattern, label)
        return score > 0

    def _any_descendant_matches(self, parent_index: QModelIndex) -> bool:
        """Iteratively scan descendant teams for a match without deep recursion.

        Criteria:
        - Team label must match pattern (if any)
        - Parent division must satisfy chip meta filters
        - Team must satisfy active-only constraint (if enabled)
        """
        stack: List[QModelIndex] = [parent_index]
        sm = self.sourceModel()
        while stack:
            current = stack.pop()
            rows = sm.rowCount(current)  # type: ignore
            for r in range(rows):
                child = sm.index(r, 0, current)  # type: ignore
                node = sm.data(child, Qt.ItemDataRole.UserRole)  # type: ignore
                if not node:
                    continue
                if getattr(node, "kind", None) == "team":
                    # Division meta check on its parent division (one level up)
                    parent_div_label = node.parent.label if node.parent else ""
                    if not self._division_meta_pass(parent_div_label):
                        continue
                    if self._active_only and "(inactive)" in node.label.lower():
                        continue
                    if self._pattern and not self._match_team_label(node.label):
                        continue
                    # Passed all filters
                    return True
                elif getattr(node, "kind", None) == "division":
                    # Skip entire subtree if division meta fails.
                    if not self._division_meta_pass(node.label):
                        continue
                    stack.append(child)
        return False


__all__ = ["NavigationFilterProxyModel"]
