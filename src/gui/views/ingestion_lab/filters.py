"""Filtering logic for the ingestion lab file navigator."""

from __future__ import annotations

import os
import time
from typing import Set

from PyQt6.QtCore import Qt

__all__ = ["FilteringMixin"]


class FilteringMixin:
    """Encapsulate in-memory filtering of file tree items."""

    def _apply_filters(self) -> None:
        if not self._all_file_items:
            return
        text = (self.search_box.text() or "").lower()
        min_kb = self.min_size.value()
        max_kb = self.max_size.value() or None
        hours = self.modified_within_hours.value()
        allowed_phases: Set[str] = {pid for pid, cb in self._phase_checks.items() if cb.isChecked()}
        now = time.time() if hours else None
        parents = []
        for item in self._all_file_items:
            data = item.data(0, Qt.ItemDataRole.UserRole) or {}
            phase = data.get("phase") if isinstance(data, dict) else None
            rel = item.text(1)
            hash_short = item.text(3)
            size_txt = item.text(2)
            visible = True
            if phase and phase not in allowed_phases:
                visible = False
            if visible and text:
                hay = f"{rel.lower()} {hash_short.lower()}"
                if text not in hay:
                    visible = False
            if visible:
                try:
                    size_val = float(size_txt) if size_txt and size_txt != "?" else 0.0
                except Exception:
                    size_val = 0.0
                if size_val < min_kb:
                    visible = False
                if max_kb is not None and max_kb > 0 and size_val > max_kb:
                    visible = False
            if visible and hours and rel:
                abs_path = os.path.join(self._base_dir, rel)
                try:
                    st = os.stat(abs_path)
                    if now and (now - st.st_mtime) > hours * 3600:
                        visible = False
                except Exception:
                    pass
            item.setHidden(not visible)
            parent = item.parent()
            if parent and parent not in parents:
                parents.append(parent)
        for p in parents:
            child_visible = any(not p.child(i).isHidden() for i in range(p.childCount()))
            p.setHidden(not child_visible)

    def filtered_file_count(self) -> int:
        return sum(1 for it in self._all_file_items if not it.isHidden())
