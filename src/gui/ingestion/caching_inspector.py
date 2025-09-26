"""Caching Inspector (Milestone 7.10.40)

Provides a lightweight backend + dialog to inspect which HTML assets would be
skipped via cache (unchanged hash vs provenance) and which would require
re-parse. This largely reuses the hash comparison logic but exposes it as a
stand‑alone pure function for easier unit testing and future extension (e.g.,
rule-sensitive reparse heuristics).

The dialog surfaces summary counts plus per‑category listings (first N items)
and can later evolve to allow force-parse selection (not in this initial pass).
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, Iterable, Mapping, List

try:  # pragma: no cover - dialog import guard
    from gui.components.chrome_dialog import ChromeDialog
except Exception:  # pragma: no cover
    ChromeDialog = object  # type: ignore[misc]

from PyQt6.QtWidgets import (
    QVBoxLayout,
    QListWidget,
    QListWidgetItem,
    QPushButton,
    QHBoxLayout,
    QLabel,
)

__all__ = ["CachingDiff", "diff_provenance", "CachingInspectorDialog"]


@dataclass
class CachingDiff:
    """Result of comparing current file hashes to provenance stored hashes.

    Attributes
    ----------
    updated: list[str]
        Files present in provenance whose current content hash differs.
    unchanged: list[str]
        Files whose hash matches provenance (eligible for skip path).
    new: list[str]
        Files present locally but absent from provenance (first-time ingest).
    missing: list[str]
        Paths recorded in provenance but no longer on disk.
    """

    updated: List[str]
    unchanged: List[str]
    new: List[str]
    missing: List[str]

    def summary(self) -> str:  # pragma: no cover - formatting
        return (
            f"Updated {len(self.updated)} | Unchanged {len(self.unchanged)} | "
            f"New {len(self.new)} | Missing {len(self.missing)}"
        )


def diff_provenance(current_files: Mapping[str, str], provenance: Mapping[str, str]) -> CachingDiff:
    """Compute caching diff using sha1 maps.

    Parameters
    ----------
    current_files: mapping str->sha1
        All discovered HTML files and their freshly computed sha1 hashes.
    provenance: mapping str->sha1
        Stored provenance mapping of previously ingested files to recorded hash.

    Returns
    -------
    CachingDiff
        Classified lists enabling skip/re-parse decisions.
    """
    current_paths = set(current_files.keys())
    prov_paths = set(provenance.keys())
    missing = sorted(prov_paths - current_paths)
    new = sorted(current_paths - prov_paths)
    updated: List[str] = []
    unchanged: List[str] = []
    for path in sorted(current_paths & prov_paths):
        if provenance[path] == current_files[path]:
            unchanged.append(path)
        else:
            updated.append(path)
    return CachingDiff(updated=updated, unchanged=unchanged, new=new, missing=missing)


class CachingInspectorDialog(ChromeDialog):  # type: ignore[misc]
    """Simple viewer listing caching categories.

    Accepts a prepared ``CachingDiff`` so the panel can compute hashes using
    its existing file scanning facilities. Keeps dialog UI passive.
    """

    def __init__(self, diff: CachingDiff, parent=None):  # noqa: D401
        super().__init__(parent, title="Caching Inspector")
        self.setObjectName("CachingInspectorDialog")
        try:  # pragma: no cover
            self.resize(600, 480)
        except Exception:
            pass
        lay = self.content_layout() if hasattr(self, "content_layout") else QVBoxLayout(self)
        lay.addWidget(QLabel(diff.summary()))
        self.listing = QListWidget()
        lay.addWidget(self.listing, 1)
        close_bar = QHBoxLayout()
        close_bar.addStretch(1)
        btn_close = QPushButton("Close")
        close_bar.addWidget(btn_close)
        lay.addLayout(close_bar)
        try:  # pragma: no cover
            btn_close.clicked.connect(self.close)  # type: ignore[attr-defined]
        except Exception:
            pass
        self._populate(diff)

    def _populate(self, diff: CachingDiff) -> None:  # noqa: D401
        self._add_section("Updated (will re-parse)", diff.updated)
        self._add_section("Unchanged (skip path)", diff.unchanged)
        self._add_section("New (first ingest)", diff.new)
        self._add_section("Missing (stale provenance)", diff.missing)

    def _add_section(self, title: str, items: Iterable[str]) -> None:
        items = list(items)
        QListWidgetItem(title, self.listing)
        if not items:
            QListWidgetItem("  (none)", self.listing)
            return
        for p in items[:50]:  # cap for readability
            QListWidgetItem("  " + p, self.listing)
        if len(items) > 50:
            QListWidgetItem(f"  (+{len(items) - 50} more)", self.listing)
