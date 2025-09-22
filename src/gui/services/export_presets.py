"""Export Presets Service (Milestone 5.6.1)

Manages named export presets that define a subset (and ordering) of columns
to include when exporting tabular data. Presets are stored in a JSON file in
the provided base directory.

Structure of persisted JSON:
{
  "version": 1,
  "presets": [
       {"name": "minimal", "columns": ["Player", "LivePZ"]},
       {"name": "trend_only", "columns": ["Player", "Trend"]}
  ]
}

Design:
 - Simple dataclass `ExportPreset` for clarity
 - Service handles load/save with graceful error handling
 - Column filtering is performed by `apply_to_export_service` helper which
   delegates to `ExportService.export(..., included_columns=...)`

Testing focuses on round-trip persistence and filtering behavior.
"""

from __future__ import annotations
from dataclasses import dataclass, asdict
from typing import List, Sequence
import json
from pathlib import Path

from .export_service import ExportService, ExportFormat

__all__ = ["ExportPreset", "ExportPresetsService"]


@dataclass
class ExportPreset:
    name: str
    columns: List[str]


class ExportPresetsService:
    def __init__(self, base_dir: str):
        self.base_dir = Path(base_dir)
        self.path = self.base_dir / "export_presets.json"
        self._presets: List[ExportPreset] = []
        self._loaded = False

    # Persistence ---------------------------------------------------
    def load(self):
        if self._loaded:
            return
        if not self.path.exists():
            self._presets = []
            self._loaded = True
            return
        try:
            data = json.loads(self.path.read_text(encoding="utf-8"))
            raw_list = data.get("presets", [])
            self._presets = [
                ExportPreset(p.get("name", "Unnamed"), list(p.get("columns", []))) for p in raw_list
            ]
        except Exception:
            self._presets = []  # fallback to empty on corruption
        self._loaded = True

    def save(self):
        payload = {
            "version": 1,
            "presets": [asdict(p) for p in self._presets],
        }
        try:
            self.base_dir.mkdir(parents=True, exist_ok=True)
            self.path.write_text(
                json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8"
            )
        except Exception:
            pass  # silent failure acceptable for now

    # CRUD ----------------------------------------------------------
    def all(self) -> List[ExportPreset]:  # pragma: no cover - trivial
        self.load()
        return list(self._presets)

    def add_or_replace(self, name: str, columns: Sequence[str]):
        self.load()
        # Remove existing with same name
        self._presets = [p for p in self._presets if p.name != name]
        self._presets.append(ExportPreset(name=name, columns=list(columns)))
        self.save()

    def delete(self, name: str):  # pragma: no cover - simple
        self.load()
        self._presets = [p for p in self._presets if p.name != name]
        self.save()

    def get(self, name: str) -> ExportPreset | None:  # pragma: no cover - simple
        self.load()
        for p in self._presets:
            if p.name == name:
                return p
        return None

    # Application ---------------------------------------------------
    def apply(self, export_service: ExportService, widget, fmt: str, preset_name: str):
        """Export using a named preset (column subset).

        Falls back to full export if preset missing.
        """
        self.load()
        preset = self.get(preset_name)
        if not preset:
            return export_service.export(widget, fmt)
        return export_service.export(widget, fmt, included_columns=preset.columns)
