"""Rule Extraction Snapshot Generator (Milestone 7.10.24)

Provides utilities to persist deterministic JSON snapshots of extraction
outputs to support regression testing of rule sets. A snapshot includes:

    - metadata: ruleset_version, created_at (iso), file_count
    - per_file: flattened rows per resource

Directory Layout (default): tests/ingestion_snapshots/<name>/
  - snapshot.json (manifest + aggregated structure)
  - files/<file_id>.json (optional raw per-file dumps; enabled via flag)

Design Goals:
  - Pure logic; no PyQt dependencies.
  - Deterministic ordering (sorted resource names, stable row ordering from
    preview generation input mapping order).
  - Minimal surface: single capture + verify helpers.

Out of Scope (future milestones):
  - Automated diff formatting UI.
  - Binary artifact storage / compression.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Mapping, Dict, Any, List, Sequence
import json
import os
from datetime import datetime

from .rule_schema import RuleSet
from .rule_parse_preview import generate_parse_preview

__all__ = [
    "SnapshotCapture",
    "generate_snapshot",
    "save_snapshot",
    "load_snapshot",
    "compare_snapshot",
]


@dataclass
class SnapshotCapture:
    name: str
    metadata: Dict[str, Any]
    aggregated: Dict[str, List[Dict[str, Any]]]
    per_file: Dict[str, Dict[str, List[Dict[str, Any]]]]

    def to_mapping(self) -> Dict[str, Any]:  # pragma: no cover - trivial
        return {
            "name": self.name,
            "metadata": self.metadata,
            "aggregated": self.aggregated,
            "per_file": self.per_file,
        }


def generate_snapshot(
    name: str,
    rule_set: RuleSet,
    html_by_file: Mapping[str, str],
    *,
    apply_transforms: bool = False,
) -> SnapshotCapture:
    # Aggregate per resource across files preserving file order then resource order.
    aggregated: Dict[str, List[Dict[str, Any]]] = {r: [] for r in sorted(rule_set.resources.keys())}
    per_file: Dict[str, Dict[str, List[Dict[str, Any]]]] = {}
    for file_id, html in html_by_file.items():
        preview = generate_parse_preview(
            rule_set, html, apply_transforms=apply_transforms, capture_performance=False
        )
        file_map: Dict[str, List[Dict[str, Any]]] = {}
        for r in sorted(rule_set.resources.keys()):
            rows = [dict(row) for row in preview.flattened_tables.get(r, [])]
            file_map[r] = rows
            aggregated[r].extend(rows)
        per_file[file_id] = file_map
    metadata = {
        "ruleset_version": rule_set.version,
        "created_at": datetime.utcnow().isoformat(timespec="seconds") + "Z",
        "file_count": len(html_by_file),
    }
    return SnapshotCapture(name=name, metadata=metadata, aggregated=aggregated, per_file=per_file)


def save_snapshot(capture: SnapshotCapture, root_dir: str, *, include_per_file: bool = False) -> str:
    target_dir = os.path.join(root_dir, capture.name)
    os.makedirs(target_dir, exist_ok=True)
    manifest_path = os.path.join(target_dir, "snapshot.json")
    with open(manifest_path, "w", encoding="utf-8") as fh:
        json.dump(
            {
                "metadata": capture.metadata,
                "aggregated": capture.aggregated,
                "per_file_included": include_per_file,
            },
            fh,
            indent=2,
            sort_keys=True,
            ensure_ascii=False,
        )
    if include_per_file:
        files_dir = os.path.join(target_dir, "files")
        os.makedirs(files_dir, exist_ok=True)
        for fid, data in capture.per_file.items():
            safe_id = fid.replace(os.sep, "__")
            with open(os.path.join(files_dir, f"{safe_id}.json"), "w", encoding="utf-8") as fh:
                json.dump(data, fh, indent=2, sort_keys=True, ensure_ascii=False)
    return manifest_path


def load_snapshot(path: str) -> Dict[str, Any]:
    with open(path, "r", encoding="utf-8") as fh:
        return json.load(fh)


def compare_snapshot(
    capture: SnapshotCapture, loaded: Mapping[str, Any]
) -> Dict[str, Sequence[str]]:
    """Compare a live snapshot capture with a loaded manifest.

    Returns mapping containing lists of difference descriptions keyed by category.
    Categories: missing_resource, extra_resource, row_mismatch.
    """
    diffs: Dict[str, List[str]] = {"missing_resource": [], "extra_resource": [], "row_mismatch": []}
    loaded_aggr: Mapping[str, Any] = loaded.get("aggregated", {})  # type: ignore[assignment]
    # Resource presence diffs
    for r in capture.aggregated.keys():
        if r not in loaded_aggr:
            diffs["missing_resource"].append(r)
    for r in loaded_aggr.keys():  # type: ignore[attr-defined]
        if r not in capture.aggregated:
            diffs["extra_resource"].append(r)
    # Row content diffs (length + ordered content string compare)
    for r, rows in capture.aggregated.items():
        if r not in loaded_aggr:
            continue
        loaded_rows = loaded_aggr.get(r, [])
        if len(rows) != len(loaded_rows):
            diffs["row_mismatch"].append(f"{r}: row count {len(rows)} != {len(loaded_rows)}")
            continue
        for idx, row in enumerate(rows):
            if dict(row) != dict(loaded_rows[idx]):
                diffs["row_mismatch"].append(f"{r}[{idx}] mismatch")
                break
    return {k: tuple(v) for k, v in diffs.items()}
