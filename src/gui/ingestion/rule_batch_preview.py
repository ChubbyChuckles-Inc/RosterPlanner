"""Multi-File Batch Parse Preview (Milestone 7.10.17)

Aggregates extraction results of a ``RuleSet`` across multiple HTML documents
to provide an overview useful for assessing rule generality before applying
changes. Reuses the single-file preview logic and focuses on deterministic,
pure computation (no side effects or DB writes).

Scope (initial):
 - For each resource (table/list) collect all extracted row records from each
   file.
 - Compute per-file stats: number of records, how many were newly added to the
   aggregate vs already seen (overlapping).
 - Compute per-resource aggregate stats: total records encountered, number of
   unique records (distinct row dicts), count of duplicate occurrences.
 - Maintain stable first-seen ordering of unique aggregated records (useful
   for downstream diff/inspection views).
 - Optional transform application (forwarded to single-file preview) for list
   rules to mirror single-file behavior.

Future extensions (later milestones, e.g. 7.10.18+):
 - Rich per-field diffing of overlapping but differing rows.
 - Sampling of changed fields, semantic key inference.
 - Performance metrics & error channel integration.

Design Notes:
 - Row identity hashing: convert each record dict into a tuple of sorted
   (key, value) items ensuring stable hashing independent of insertion order.
 - Missing resources in a file produce a zero-count stat entry (keeps matrix
   shape uniform for UI table rendering simplicity).
 - Keeps dependency surface minimal and test friendly.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict, List, Mapping, Tuple
import time
import tracemalloc

from .rule_schema import RuleSet, TableRule, ListRule
from .rule_parse_preview import generate_parse_preview

__all__ = [
    "BatchFileResourceStats",
    "BatchResourceAggregate",
    "BatchPreviewResult",
    "generate_batch_preview",
]


def _row_key(row: Mapping[str, Any]) -> Tuple[Tuple[str, Any], ...]:
    """Create a deterministic hashable key for a row mapping."""
    # Sorting ensures consistent ordering; values are taken as-is (hashable or not).
    # For unhashable values (like lists) we fall back to str() representation.
    norm_items: List[Tuple[str, Any]] = []
    for k, v in sorted(row.items()):
        try:
            hash(v)  # type: ignore[arg-type]
            norm_items.append((k, v))
        except Exception:  # pragma: no cover - rare path
            norm_items.append((k, repr(v)))
    return tuple(norm_items)


@dataclass
class BatchFileResourceStats:
    file: str
    resource: str
    record_count: int
    added: int
    overlapping: int

    def to_mapping(self) -> Mapping[str, Any]:  # pragma: no cover - trivial
        return {
            "file": self.file,
            "resource": self.resource,
            "record_count": self.record_count,
            "added": self.added,
            "overlapping": self.overlapping,
        }


@dataclass
class BatchResourceAggregate:
    resource: str
    total_records: int
    unique_records: int
    duplicate_records: int

    def to_mapping(self) -> Mapping[str, Any]:  # pragma: no cover - trivial
        return {
            "resource": self.resource,
            "total_records": self.total_records,
            "unique_records": self.unique_records,
            "duplicate_records": self.duplicate_records,
        }


@dataclass
class BatchPreviewResult:
    resource_aggregates: List[BatchResourceAggregate]
    file_resource_stats: List[BatchFileResourceStats]
    aggregated_records: Dict[str, List[Mapping[str, Any]]]
    duplicate_counts: Dict[str, int]
    total_parse_time_ms: float
    total_node_count: int
    peak_memory_kb: float

    def to_mapping(self) -> Mapping[str, Any]:  # pragma: no cover - trivial
        return {
            "resource_aggregates": [a.to_mapping() for a in self.resource_aggregates],
            "file_resource_stats": [s.to_mapping() for s in self.file_resource_stats],
            "aggregated_records": self.aggregated_records,
            "duplicate_counts": dict(self.duplicate_counts),
        }


def generate_batch_preview(
    rule_set: RuleSet,
    html_by_file: Mapping[str, str],
    *,
    apply_transforms: bool = False,
    capture_performance: bool = True,
) -> BatchPreviewResult:
    """Generate an aggregated multi-file preview.

    Parameters
    ----------
    rule_set : RuleSet
        Active rule set to apply to each HTML document.
    html_by_file : Mapping[str, str]
        Mapping of file identifier (path or logical name) -> raw HTML text.
    apply_transforms : bool, default False
        Forwarded to underlying single-file preview (affects list rule field transforms).
    """

    # Initialize structures per resource
    aggregated_records: Dict[str, List[Mapping[str, Any]]] = {
        r: [] for r in rule_set.resources.keys()
    }
    seen_keys: Dict[str, set] = {r: set() for r in rule_set.resources.keys()}
    duplicate_counts: Dict[str, int] = {r: 0 for r in rule_set.resources.keys()}
    file_stats: List[BatchFileResourceStats] = []

    # Iterate files in insertion order of mapping
    total_time = 0.0
    total_nodes = 0
    peak_mem = 0.0
    if capture_performance:
        tracemalloc.start()
    for file_id, html in html_by_file.items():
        preview = generate_parse_preview(
            rule_set,
            html,
            apply_transforms=apply_transforms,
            capture_performance=capture_performance,
        )
        total_time += preview.parse_time_ms
        total_nodes += preview.node_count
        if capture_performance:
            current, peak = tracemalloc.get_traced_memory()
            peak_mem = max(peak_mem, peak / 1024.0)
        # Build lookup from summaries for quick record counts
        rec_map = preview.extracted_records
        # Ensure all resources present even if empty
        for r_name in rule_set.resources.keys():
            rows = list(rec_map.get(r_name, []))
            added = 0
            overlapping = 0
            for row in rows:
                key = _row_key(row)
                if key in seen_keys[r_name]:
                    overlapping += 1
                    duplicate_counts[r_name] += 1
                else:
                    seen_keys[r_name].add(key)
                    aggregated_records[r_name].append(row)
                    added += 1
            file_stats.append(
                BatchFileResourceStats(
                    file=file_id,
                    resource=r_name,
                    record_count=len(rows),
                    added=added,
                    overlapping=overlapping,
                )
            )

    resource_aggregates: List[BatchResourceAggregate] = []
    for r_name in rule_set.resources.keys():
        total = sum(s.record_count for s in file_stats if s.resource == r_name)
        uniq = len(aggregated_records[r_name])
        dup = duplicate_counts[r_name]
        resource_aggregates.append(
            BatchResourceAggregate(
                resource=r_name,
                total_records=total,
                unique_records=uniq,
                duplicate_records=dup,
            )
        )

    if capture_performance:
        tracemalloc.stop()
    return BatchPreviewResult(
        resource_aggregates=resource_aggregates,
        file_resource_stats=file_stats,
        aggregated_records=aggregated_records,
        duplicate_counts=duplicate_counts,
        total_parse_time_ms=total_time,
        total_node_count=total_nodes,
        peak_memory_kb=peak_mem,
    )
