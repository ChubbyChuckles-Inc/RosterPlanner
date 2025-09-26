"""Export Presets Service (Milestones 5.6.1 / 7.10.64)

Manages named export presets that define a subset (and ordering) of columns
to include when exporting tabular data. Presets are stored in a JSON file in
the provided base directory.

Structure of persisted JSON::

        {
            "version": 1,
            "presets": [
                     {"name": "minimal", "columns": ["Player", "LivePZ"]},
                     {"name": "trend_only", "columns": ["Player", "Trend"]},
                     {"name": "with_derived", "columns": ["Player", "*derived"]}
            ]
        }

Milestone 7.10.64 adds support for a dynamic placeholder token ``*derived``.
If present in a preset's column list it is expanded (in place) to the current
set of rule‑set derived field names defined under the top‑level ``derived``
mapping of the *active* ingestion rule set (latest version loaded via the
optional ``rule_version_store`` service). This keeps presets stable while
allowing new derived fields to automatically appear without manual editing.

Design:
 - Simple dataclass `ExportPreset` for clarity
 - Service handles load/save with graceful error handling
 - Dynamic column expansion (``*derived``) resolved at apply time, never
     persisted as explicit field names (ensuring new derived fields appear)
 - Column filtering delegated to :class:`ExportService` via ``included_columns``

Failure & Safety:
 - If the rule set store or JSON is unavailable / malformed the placeholder
     expands to an empty list (effectively removing it) and export proceeds.
 - Unknown / duplicate column names are ignored by the export layer naturally.

Testing focuses on round-trip persistence, filtering behavior, and dynamic
placeholder expansion.
"""

from __future__ import annotations
from dataclasses import dataclass, asdict
from typing import List, Sequence, Iterable
import json
from pathlib import Path

from .export_service import ExportService, ExportFormat
from .service_locator import services

# Special placeholder token for rule-derived fields (Milestone 7.10.64)
DERIVED_PLACEHOLDER = "*derived"

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
        resolved = self._resolve_dynamic_columns(preset.columns)
        return export_service.export(widget, fmt, included_columns=resolved)

    # Dynamic resolution ------------------------------------------------
    def _resolve_dynamic_columns(self, columns: Sequence[str]) -> List[str]:
        """Resolve dynamic placeholder tokens within a preset column list.

        Currently supports one token: ``*derived`` which is expanded in-place
        to the list of derived field names declared in the active rule set
        (if any). Ordering of derived fields preserves the order in the
        source JSON mapping for determinism.

        Parameters
        ----------
        columns: Sequence[str]
            Original preset column entries (may contain placeholders).

        Returns
        -------
        List[str]
            Concrete column names with placeholders expanded.
        """
        out: List[str] = []
        for col in columns:
            if col == DERIVED_PLACEHOLDER:
                out.extend(self._current_derived_fields())
            else:
                out.append(col)
        # Deduplicate while preserving order (in case derived overlaps)
        seen = set()
        dedup: List[str] = []
        for c in out:
            if c in seen:
                continue
            seen.add(c)
            dedup.append(c)
        return dedup

    def _current_derived_fields(self) -> List[str]:
        """Return list of derived field names from active rule set.

        Attempts to retrieve a ``rule_version_store`` service which is
        expected to expose a ``latest()`` method returning an object with
        a ``rules_json`` attribute (compatible with ``RuleSetVersionStore``).
        Gracefully falls back to empty list on any error.
        """
        try:  # pragma: no cover - guard path mostly hit in integration
            store = services.try_get("rule_version_store")
            if not store:
                return []
            latest = None
            if hasattr(store, "latest") and callable(getattr(store, "latest")):
                latest = store.latest()
            elif hasattr(store, "latest_version"):
                latest = getattr(store, "latest_version")
            if not latest:
                return []
            raw = getattr(latest, "rules_json", None)
            if not isinstance(raw, str):
                return []
            data = json.loads(raw or "{}")
            derived = data.get("derived")
            if isinstance(derived, dict):
                # Preserve source order (Python 3.7+ dict ordering)
                return [k for k in derived.keys() if isinstance(k, str)]
            return []
        except Exception:
            return []
