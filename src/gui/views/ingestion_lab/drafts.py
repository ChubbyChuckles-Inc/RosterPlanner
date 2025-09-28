"""Draft autosave and publish helpers for the ingestion lab panel."""

from __future__ import annotations

import hashlib
import json
import os
import time
from dataclasses import dataclass
from datetime import datetime
from typing import Any, Dict, List, Optional

try:  # pragma: no cover
    from gui.services.service_locator import services as _services  # type: ignore
except Exception:  # pragma: no cover
    _services = None  # type: ignore

__all__ = ["DraftSnapshot", "DraftingMixin"]


@dataclass(frozen=True)
class DraftSnapshot:
    """Immutable representation of a stored draft autosave snapshot."""

    timestamp: int
    content_hash: str
    text: str

    def label(self) -> str:
        dt = datetime.fromtimestamp(self.timestamp)
        return dt.strftime("%Y-%m-%d %H:%M:%S")

    def short_hash(self) -> str:
        return self.content_hash[:10]


class DraftingMixin:
    """Manage rule editor draft lifecycle and publishing."""

    def _on_rule_text_changed(self) -> None:  # pragma: no cover - GUI event
        self._draft_dirty = True
        if getattr(self, "_intent_refresh_timer", None):
            try:
                self._intent_refresh_timer.start()  # type: ignore[operator]
            except Exception:
                pass

    def _autosave_draft(self) -> None:
        if not self._draft_dirty:
            return
        text = self.rule_editor.toPlainText()
        if not (text and text.strip()):
            return
        try:
            tmp_path = self._draft_path + ".tmp"
            with open(tmp_path, "w", encoding="utf-8", errors="ignore") as fh:
                json.dump({"text": text, "ts": int(time.time())}, fh, ensure_ascii=False, indent=2)
            os.replace(tmp_path, self._draft_path)
            self._draft_dirty = False
            self._append_log("Draft autosaved")
            self._record_draft_snapshot(text)
        except Exception as e:  # pragma: no cover
            try:
                self._append_log(f"Draft autosave WARN: {e}")
            except Exception:
                pass

    def _load_existing_draft(self) -> None:
        if not os.path.exists(self._draft_path):
            return
        current = self.rule_editor.toPlainText()
        if current.strip():
            return
        try:
            with open(self._draft_path, "r", encoding="utf-8", errors="ignore") as fh:
                payload = json.load(fh)
            if isinstance(payload, dict) and isinstance(payload.get("text"), str):
                self.rule_editor.setPlainText(payload.get("text", ""))
                self._draft_dirty = False
                self._append_log("Draft restored")
        except Exception as e:  # pragma: no cover
            self._append_log(f"Draft restore WARN: {e}")

    def _on_publish_clicked(self) -> None:
        raw = (self.rule_editor.toPlainText() or "").strip()
        if not raw:
            self._append_log("Publish: editor empty")
            return
        try:
            content_hash = hashlib.sha1(raw.encode("utf-8", "ignore")).hexdigest()
        except Exception as e:  # pragma: no cover
            self._append_log(f"Publish ERROR (hash): {e}")
            return
        if content_hash == self._last_published_hash:
            self._append_log("Publish: no changes since last publish")
            return
        try:
            js = json.loads(raw) if raw else {}
            if not isinstance(js, dict):
                raise ValueError("Root must be a JSON object")
        except Exception as e:
            self._append_log(f"Publish ERROR (parse): {e}")
            return
        conn = None
        if _services is not None:
            try:
                conn = _services.try_get("sqlite_conn")
            except Exception:
                conn = None
        version_num = None
        if conn is not None:
            try:
                from gui.ingestion.rule_versioning import RuleSetVersionStore

                store = RuleSetVersionStore(conn)
                version_num = store.save_version(js, raw)
            except Exception as e:  # pragma: no cover
                self._append_log(f"Publish WARN (version store): {e}")
        self._last_published_hash = content_hash
        try:
            if os.path.exists(self._draft_path):
                os.remove(self._draft_path)
        except Exception:  # pragma: no cover
            pass
        self._draft_dirty = False
        msg = f"Published draft (hash={content_hash[:10]})"
        if version_num is not None:
            msg += f" -> v{version_num}"
            self._last_version_num = version_num
        self._append_log(msg)
        if _services is not None:
            try:
                from gui.services.event_bus import GUIEvent, EventBus

                bus: "EventBus" | None = _services.try_get("event_bus")  # type: ignore[name-defined]
                if bus:
                    bus.publish(
                        GUIEvent.INGEST_RULES_PUBLISHED,
                        {"hash": content_hash, "version": version_num},
                    )
            except Exception:  # pragma: no cover
                pass

    # ------------------------------------------------------------------
    # Draft history helpers

    def _record_draft_snapshot(self, text: str) -> None:
        path = getattr(self, "_draft_history_path", None)
        if not path:
            return
        try:
            content_hash = hashlib.sha1(text.encode("utf-8", "ignore")).hexdigest()
        except Exception:
            content_hash = ""
        entries = self._load_draft_history_entries()
        timestamp = int(time.time())
        if entries and entries[-1]["hash"] == content_hash:
            entries[-1] = {"ts": timestamp, "hash": content_hash, "text": text}
        else:
            entries.append({"ts": timestamp, "hash": content_hash, "text": text})
        max_entries = getattr(self, "_draft_history_max_entries", 5)
        if max_entries > 0:
            entries = entries[-max_entries:]
        try:
            tmp_path = path + ".tmp"
            payload = {"entries": entries}
            with open(tmp_path, "w", encoding="utf-8", errors="ignore") as fh:
                json.dump(payload, fh, ensure_ascii=False, indent=2)
            os.replace(tmp_path, path)
        except Exception:  # pragma: no cover
            return
        if hasattr(self, "_timeline_refresh_snapshots"):
            try:
                self._timeline_refresh_snapshots()  # type: ignore[attr-defined]
            except Exception:
                pass

    def _load_draft_history_entries(self) -> List[Dict[str, Any]]:
        path = getattr(self, "_draft_history_path", None)
        if not path or not os.path.exists(path):
            return []
        try:
            with open(path, "r", encoding="utf-8", errors="ignore") as fh:
                payload = json.load(fh)
        except Exception:
            return []
        raw_entries: List[Dict[str, Any]] = []
        items = payload.get("entries") if isinstance(payload, dict) else payload
        if not isinstance(items, list):
            return []
        for entry in items:
            if not isinstance(entry, dict):
                continue
            text = entry.get("text")
            ts = entry.get("ts")
            if not isinstance(text, str) or not isinstance(ts, int):
                continue
            hash_value = entry.get("hash")
            if not isinstance(hash_value, str) or not hash_value:
                try:
                    hash_value = hashlib.sha1(text.encode("utf-8", "ignore")).hexdigest()
                except Exception:
                    hash_value = ""
            raw_entries.append({"ts": ts, "hash": hash_value, "text": text})
        raw_entries.sort(key=lambda item: item["ts"])
        return raw_entries

    def _get_recent_draft_snapshots(self, limit: Optional[int] = None) -> List[DraftSnapshot]:
        entries = self._load_draft_history_entries()
        snapshots = [
            DraftSnapshot(timestamp=entry["ts"], content_hash=entry["hash"], text=entry["text"])
            for entry in entries
        ]
        snapshots.sort(key=lambda snap: snap.timestamp, reverse=True)
        if limit is not None and limit >= 0:
            snapshots = snapshots[:limit]
        return snapshots
