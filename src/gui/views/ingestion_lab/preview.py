"""Preview and rule parsing helpers for the ingestion lab panel."""

from __future__ import annotations

import json
import os
from typing import Dict

from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import QApplication

__all__ = ["PreviewMixin"]


class PreviewMixin:
    """Provide file preview rendering and rule parsing helpers."""

    def _on_file_selection_changed(self) -> None:
        items = self.file_tree.selectedItems()
        enabled = False
        if items:
            data = items[0].data(0, Qt.ItemDataRole.UserRole)
            if isinstance(data, dict) and "file" in data:
                enabled = True
        self.btn_preview.setEnabled(enabled)

    def _on_preview_clicked(self) -> None:
        items = [
            it
            for it in self.file_tree.selectedItems()
            if isinstance(it.data(0, Qt.ItemDataRole.UserRole), dict)
            and "file" in it.data(0, Qt.ItemDataRole.UserRole)
        ]
        if not items:
            return
        if len(items) == 1:
            self._single_preview(items[0])
        else:
            self._batch_preview(items)

    def _single_preview(self, target) -> None:
        start = self._now()
        payload = target.data(0, Qt.ItemDataRole.UserRole)
        fpath = payload.get("file")
        self._last_preview_html = ""
        try:
            stat = os.stat(fpath)
            with open(fpath, "r", encoding="utf-8", errors="replace") as fh:
                html_full = fh.read()
            snippet = html_full[:800]
            prov_payload = target.data(2, Qt.ItemDataRole.UserRole) or {}
            if isinstance(prov_payload, dict):
                hash_full = prov_payload.get("hash")
                last_ingested = prov_payload.get("last_ingested_at")
                parser_ver = prov_payload.get("parser_version")
            else:  # pragma: no cover
                hash_full = last_ingested = parser_ver = None
            meta = [
                f"File: {fpath}",
                f"Size: {stat.st_size} bytes",
                f"Modified: {int(stat.st_mtime)} (epoch)",
            ]
            if hash_full:
                meta.append(f"Hash: {hash_full}")
            if last_ingested:
                meta.append(f"Last Ingested: {last_ingested}")
            if parser_ver:
                meta.append(f"Parser Version: {parser_ver}")
            meta.extend(["--- Snippet ---", snippet])
            plain = "\n".join(meta)
            self._last_preview_plain = plain
            self._last_preview_html = html_full
            self.preview_area.setPlainText(plain)
            try:
                if hasattr(self, "visual_builder") and hasattr(
                    self.visual_builder, "set_preview_html"
                ):
                    self.visual_builder.set_preview_html(html_full)  # type: ignore[attr-defined]
            except Exception:
                pass
            try:
                rel_name = target.text(1) or target.text(0)
            except Exception:
                rel_name = fpath
            try:
                if hasattr(self, "_record_dead_field_snapshot"):
                    self._record_dead_field_snapshot(fpath, html_full)  # type: ignore[attr-defined]
            except Exception:
                pass
            self._append_log(f"Previewed: {rel_name}")
        except Exception as e:  # pragma: no cover
            err = f"Error reading file: {e}"
            self._last_preview_plain = err
            self._last_preview_html = ""
            self.preview_area.setPlainText(err)
            try:
                if hasattr(self, "visual_builder") and hasattr(
                    self.visual_builder, "set_preview_html"
                ):
                    self.visual_builder.set_preview_html("")  # type: ignore[attr-defined]
            except Exception:
                pass
            try:
                rel_name = target.text(1) or target.text(0)
            except Exception:
                rel_name = "<unknown>"
            self._append_log(f"ERROR preview {rel_name}: {e}")
        elapsed_ms = (self._now() - start) * 1000.0
        self._update_performance_badge(elapsed_ms)
        try:
            from gui.services.telemetry_service import TelemetryService  # type: ignore

            TelemetryService.instance.record_preview(elapsed_ms)
        except Exception:
            pass

    def _batch_preview(self, targets: list) -> None:
        start = self._now()
        count = len(targets)
        self._last_preview_html = ""
        use_skeleton = count >= self.batch_preview_skeleton_min_files
        if use_skeleton:
            try:
                if hasattr(self._batch_skeleton, "_rows") and hasattr(
                    self._batch_skeleton, "start"
                ):
                    self._preview_stack.setCurrentIndex(1)
                    self._batch_skeleton_last_shown = True
                    if hasattr(self._batch_skeleton, "start"):
                        try:
                            self._batch_skeleton.start()  # type: ignore[attr-defined]
                        except Exception:
                            pass
            except Exception:
                pass
        out_lines = [f"Batch Preview ({count} files)"]
        try:
            from gui.services.settings_service import SettingsService  # type: ignore

            cap = int(getattr(SettingsService.instance, "ingestion_preview_batch_cap", 50))
        except Exception:
            cap = 50
        for idx, it in enumerate(targets[:cap]):
            payload = it.data(0, Qt.ItemDataRole.UserRole)
            fpath = payload.get("file") if isinstance(payload, dict) else None
            if not fpath:
                continue
            try:
                stat = os.stat(fpath)
                with open(fpath, "r", encoding="utf-8", errors="replace") as fh:
                    snippet = fh.read(200)
                out_lines.append(
                    f"[{idx+1}] {fpath} size={stat.st_size} mod={int(stat.st_mtime)} bytes snippet_len={len(snippet)}"
                )
            except Exception as e:  # pragma: no cover
                out_lines.append(f"[{idx+1}] {fpath} ERROR: {e}")
        if count > cap:
            out_lines.append(f"... truncated {count-cap} more")
        delay_ms = self.batch_preview_artificial_delay_ms
        if use_skeleton and delay_ms > 0:
            target_t = start + (delay_ms / 1000.0)
            while self._now() < target_t:
                try:
                    QApplication.processEvents()
                except Exception:
                    break
        self.preview_area.setPlainText("\n".join(out_lines))
        try:
            if hasattr(self, "visual_builder") and hasattr(self.visual_builder, "set_preview_html"):
                self.visual_builder.set_preview_html("")  # type: ignore[attr-defined]
        except Exception:
            pass
        if use_skeleton:
            try:
                if hasattr(self._batch_skeleton, "stop"):
                    self._batch_skeleton.stop()  # type: ignore[attr-defined]
            except Exception:
                pass
            self._preview_stack.setCurrentIndex(0)
        self._append_log(f"Batch preview complete: {count} files")
        elapsed_ms = (self._now() - start) * 1000.0
        self._update_performance_badge(elapsed_ms)
        try:
            from gui.services.telemetry_service import TelemetryService  # type: ignore

            TelemetryService.instance.record_preview(elapsed_ms)
        except Exception:
            pass

    def _gather_visible_file_html(self, *, selected_only: bool = False) -> Dict[str, str]:
        files: Dict[str, str] = {}

        def _iter_items():
            selected = []
            if selected_only:
                try:
                    selected = [
                        it
                        for it in self.file_tree.selectedItems()
                        if isinstance(it.data(0, Qt.ItemDataRole.UserRole), dict)
                        and "file" in it.data(0, Qt.ItemDataRole.UserRole)
                    ]
                except Exception:
                    selected = []
            if selected:
                return selected
            return [
                it
                for it in self._all_file_items
                if not it.isHidden()
                and isinstance(it.data(0, Qt.ItemDataRole.UserRole), dict)
                and "file" in it.data(0, Qt.ItemDataRole.UserRole)
            ]

        for item in _iter_items():
            data = item.data(0, Qt.ItemDataRole.UserRole)
            if not (isinstance(data, dict) and "file" in data):
                continue
            path = data.get("file")  # type: ignore[index]
            if not path:
                continue
            if path in files:
                continue
            try:
                with open(path, "r", encoding="utf-8", errors="replace") as fh:
                    files[path] = fh.read()
            except Exception:
                continue
        return files

    def _parse_ruleset_from_editor(self):  # type: ignore[override]
        from gui.ingestion.rule_schema import RuleSet, RuleError

        text = (self.rule_editor.toPlainText() or "").strip()
        if not text:
            raise ValueError("Rule editor is empty – cannot compute coverage")
        try:
            data = json.loads(text)
        except Exception as e_json:
            raise ValueError(f"Failed to parse rules JSON: {e_json}")
        try:
            return RuleSet.from_mapping(data)
        except RuleError as e:  # pragma: no cover
            raise ValueError(f"Invalid rule set: {e}") from e
