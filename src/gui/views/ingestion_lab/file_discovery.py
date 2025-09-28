"""File discovery and navigation helpers for the ingestion lab panel."""

from __future__ import annotations

import glob
import os
from typing import Dict, List

from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import QTreeWidgetItem

try:  # pragma: no cover
    from gui.services.service_locator import services as _services  # type: ignore
except Exception:  # pragma: no cover
    _services = None  # type: ignore

from .constants import OTHER_PHASE_ID, PHASE_PATTERNS

__all__ = ["FileDiscoveryMixin"]


class FileDiscoveryMixin:
    """Encapsulate file scanning and tree population."""

    def refresh_file_list(self) -> None:
        self.file_tree.clear()
        self._all_file_items.clear()
        data_root = self._base_dir
        if not os.path.isdir(data_root):  # pragma: no cover - defensive
            return
        pattern = os.path.join(data_root, "**", "*.html")
        files = sorted(glob.glob(pattern, recursive=True))
        grouped: Dict[str, List[str]] = {pid: [] for pid, _lbl, _ in PHASE_PATTERNS}
        grouped[OTHER_PHASE_ID] = []
        label_map = {pid: lbl for pid, lbl, _ in PHASE_PATTERNS}
        label_map[OTHER_PHASE_ID] = "Other"

        provenance: Dict[str, tuple[str, str, int]] = {}
        conn = None
        if _services is not None:
            try:
                conn = _services.try_get("sqlite_conn")  # type: ignore[attr-defined]
            except Exception:  # pragma: no cover
                conn = None
        if conn is not None:
            try:
                cur = conn.execute(
                    "SELECT path, sha1, COALESCE(last_ingested_at,'') as ts, COALESCE(parser_version,1) FROM provenance"
                )
                for row in cur.fetchall():
                    provenance[str(row[0])] = (str(row[1]), str(row[2]), int(row[3]))
            except Exception:  # pragma: no cover
                provenance = {}

        for fpath in files:
            rel = os.path.relpath(fpath, data_root)
            fn = os.path.basename(rel).lower()
            assigned = False
            for pid, _lbl, pred in PHASE_PATTERNS:
                try:
                    if pred(rel, fn):
                        grouped[pid].append(fpath)
                        assigned = True
                        break
                except Exception:
                    pass
            if not assigned:
                grouped[OTHER_PHASE_ID].append(fpath)
        total_files = 0
        for pid, files_in_phase in grouped.items():
            if not files_in_phase:
                continue
            phase_item = QTreeWidgetItem([label_map.get(pid, pid), "", "", "", "", ""])
            phase_item.setData(0, Qt.ItemDataRole.UserRole, {"phase": pid})
            self.file_tree.addTopLevelItem(phase_item)
            for fpath in sorted(files_in_phase):
                rel = os.path.relpath(fpath, data_root)
                try:
                    stat = os.stat(fpath)
                    size_kb = f"{stat.st_size/1024:.1f}"
                except Exception:
                    size_kb = "?"
                prov = provenance.get(fpath)
                if prov:
                    sha1, ts, parser_ver = prov
                    short_hash = sha1[:10]
                else:
                    short_hash = ""
                    ts = ""
                    parser_ver = 0
                child = QTreeWidgetItem(
                    ["", rel, size_kb, short_hash, ts, str(parser_ver) if parser_ver else "-"]
                )
                child.setData(0, Qt.ItemDataRole.UserRole, {"file": fpath, "phase": pid})
                child.setData(1, Qt.ItemDataRole.UserRole, {"file": fpath, "phase": pid})
                child.setData(
                    2,
                    Qt.ItemDataRole.UserRole,
                    {
                        "file": fpath,
                        "phase": pid,
                        "hash": prov[0] if prov else None,
                        "last_ingested_at": ts if prov else None,
                        "parser_version": parser_ver if prov else None,
                    },
                )
                phase_item.addChild(child)
                self._all_file_items.append(child)
                total_files += 1
            phase_item.setExpanded(True)
        self._last_provenance = provenance
        self._append_log(
            f"Refreshed: {total_files} HTML files across {sum(1 for v in grouped.values() if v)} phases."
        )
        self._apply_filters()

    def listed_files(self) -> List[str]:
        files: List[str] = []
        root_count = self.file_tree.topLevelItemCount()
        for r in range(root_count):
            phase_item = self.file_tree.topLevelItem(r)
            for c in range(phase_item.childCount()):
                child = phase_item.child(c)
                text = child.text(1) or child.text(0)
                if text:
                    files.append(text)
        return files

    def phases(self) -> List[str]:
        ids: List[str] = []
        for r in range(self.file_tree.topLevelItemCount()):
            item = self.file_tree.topLevelItem(r)
            data = item.data(0, Qt.ItemDataRole.UserRole)
            if isinstance(data, dict) and "phase" in data:
                ids.append(data["phase"])  # type: ignore[index]
        return ids
