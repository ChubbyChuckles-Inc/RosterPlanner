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
        if not self._pattern:
            return True
        # Kick off index build asynchronously the first time filtering occurs
        self._ensure_index()
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
