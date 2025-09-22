"""Tab Metadata Persistence Service (Milestone 5.8)

Persists lightweight metadata about open documents (currently pin state and
optional color tag) so that user preferences survive restarts.

Design:
 - JSON file: tab_metadata.json at data dir root
 - Structure:
   {
     "version": 1,
     "tabs": {
        "doc_id": {"pinned": true, "color": "#RRGGBB" | null}
     }
   }
 - Only stores metadata for tabs user has interacted with (pinned / colored).
 - Provides idempotent ensure/update helpers and safe load on startup.

Future extensions:
 - Persist tab order explicitly
 - Persist last active tab id
 - Add per-tab custom note / alias title
"""

from __future__ import annotations
from dataclasses import dataclass, asdict
from typing import Dict, Optional
import json
from pathlib import Path

__all__ = ["TabMetadata", "TabMetadataPersistenceService"]


@dataclass
class TabMetadata:
    pinned: bool = False
    color: Optional[str] = None  # hex string like '#FF8800'


class TabMetadataPersistenceService:
    def __init__(self, base_dir: str):
        self.base_dir = Path(base_dir)
        self.path = self.base_dir / "tab_metadata.json"
        self._loaded = False
        self._map: Dict[str, TabMetadata] = {}

    # Lifecycle -----------------------------------------------------
    def load(self):  # pragma: no cover - simple IO
        if self._loaded:
            return
        if not self.path.exists():
            self._loaded = True
            return
        try:
            data = json.loads(self.path.read_text(encoding="utf-8"))
            tabs = data.get("tabs", {})
            for doc_id, meta in tabs.items():
                self._map[doc_id] = TabMetadata(
                    pinned=bool(meta.get("pinned", False)),
                    color=meta.get("color"),
                )
        except Exception:
            self._map = {}
        self._loaded = True

    def save(self):  # pragma: no cover - simple IO
        try:
            self.base_dir.mkdir(parents=True, exist_ok=True)
            payload = {
                "version": 1,
                "tabs": {
                    doc_id: asdict(meta)
                    for doc_id, meta in self._map.items()
                    if meta.pinned or meta.color
                },
            }
            self.path.write_text(
                json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8"
            )
        except Exception:
            pass

    # CRUD ----------------------------------------------------------
    def get(self, doc_id: str) -> TabMetadata:
        self.load()
        return self._map.setdefault(doc_id, TabMetadata())

    def set_pinned(self, doc_id: str, pinned: bool):
        meta = self.get(doc_id)
        meta.pinned = pinned
        self.save()

    def set_color(self, doc_id: str, color: Optional[str]):
        meta = self.get(doc_id)
        meta.color = color
        self.save()

    # Query helpers -------------------------------------------------
    def pinned_ids(self):  # pragma: no cover - trivial
        self.load()
        return [doc_id for doc_id, meta in self._map.items() if meta.pinned]

    def color_for(self, doc_id: str) -> Optional[str]:  # pragma: no cover - trivial
        return self.get(doc_id).color
