"""Quick Rule Set Diff (Milestone 7.10.25)

Compares two ``RuleSet`` definitions over the same collection of HTML
documents and produces per-resource row difference metrics. Intended for
fast feedback inside the Ingestion Lab when iterating on rule changes.

Approach
--------
Each rule set is applied independently (single-file preview reused). For
each resource name present in either rule set, the flattened row dicts are
collected across all files and converted into deterministic hashable row
keys. Intersections & set differences provide overlap and unique counts.

Limitations
-----------
 - Rows considered identical only if all key/value pairs match exactly.
 - Structural changes (e.g. column removal) count as unique rows on each side.
 - No per-field change mapping yet (future enhancement could align rows by
   heuristic keys and produce changed field stats).

Return Value
------------
`diff_rule_sets` returns a ``QuickDiffResult`` containing per-resource
summaries plus global aggregate totals (sum of counts) for UI summarization.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, Mapping, Any, List, Set

from .rule_schema import RuleSet
from .rule_parse_preview import generate_parse_preview

__all__ = ["QuickDiffResource", "QuickDiffResult", "diff_rule_sets"]


def _row_key(row: Mapping[str, Any]) -> tuple:
    parts = []
    for k, v in sorted(row.items()):
        try:
            hash(v)  # type: ignore[arg-type]
            parts.append((k, v))
        except Exception:  # pragma: no cover - unhashable defensive
            parts.append((k, repr(v)))
    return tuple(parts)


@dataclass
class QuickDiffResource:
    name: str
    kind_a: str | None
    kind_b: str | None
    count_a: int
    count_b: int
    only_a: int
    only_b: int
    overlap: int

    def to_mapping(self) -> Dict[str, Any]:  # pragma: no cover - trivial
        return {
            "name": self.name,
            "kind_a": self.kind_a,
            "kind_b": self.kind_b,
            "count_a": self.count_a,
            "count_b": self.count_b,
            "only_a": self.only_a,
            "only_b": self.only_b,
            "overlap": self.overlap,
        }


@dataclass
class QuickDiffResult:
    resources: List[QuickDiffResource]
    total_only_a: int
    total_only_b: int
    total_overlap: int

    def to_mapping(self) -> Dict[str, Any]:  # pragma: no cover - trivial
        return {
            "resources": [r.to_mapping() for r in self.resources],
            "total_only_a": self.total_only_a,
            "total_only_b": self.total_only_b,
            "total_overlap": self.total_overlap,
        }


def diff_rule_sets(
    rule_set_a: RuleSet,
    rule_set_b: RuleSet,
    html_by_file: Mapping[str, str],
    *,
    apply_transforms: bool = False,
) -> QuickDiffResult:
    # Build previews for each file under both rule sets.
    aggr_a: Dict[str, List[Mapping[str, Any]]] = {r: [] for r in rule_set_a.resources.keys()}
    aggr_b: Dict[str, List[Mapping[str, Any]]] = {r: [] for r in rule_set_b.resources.keys()}
    for file_id, html in html_by_file.items():  # noqa: ARG001 - file id currently unused in diff
        prev_a = generate_parse_preview(
            rule_set_a, html, apply_transforms=apply_transforms, capture_performance=False
        )
        prev_b = generate_parse_preview(
            rule_set_b, html, apply_transforms=apply_transforms, capture_performance=False
        )
        for r, rows in prev_a.flattened_tables.items():
            aggr_a[r].extend(rows)
        for r, rows in prev_b.flattened_tables.items():
            aggr_b[r].extend(rows)

    # Union of resource names
    all_resources: Set[str] = set(aggr_a.keys()) | set(aggr_b.keys())
    summaries: List[QuickDiffResource] = []
    total_only_a = total_only_b = total_overlap = 0
    for r in sorted(all_resources):
        rows_a = aggr_a.get(r, [])
        rows_b = aggr_b.get(r, [])
        set_a = {_row_key(row) for row in rows_a}
        set_b = {_row_key(row) for row in rows_b}
        overlap_keys = set_a & set_b
        only_a_keys = set_a - set_b
        only_b_keys = set_b - set_a
        only_a = len(only_a_keys)
        only_b = len(only_b_keys)
        overlap = len(overlap_keys)
        total_only_a += only_a
        total_only_b += only_b
        total_overlap += overlap
        res_obj_a = rule_set_a.resources.get(r)
        res_obj_b = rule_set_b.resources.get(r)
        kind_a = (
            getattr(res_obj_a, "__class__", type("_", (), {})).__name__.replace("Rule", "").lower()
            if res_obj_a
            else None
        )
        kind_b = (
            getattr(res_obj_b, "__class__", type("_", (), {})).__name__.replace("Rule", "").lower()
            if res_obj_b
            else None
        )
        summaries.append(
            QuickDiffResource(
                name=r,
                kind_a=kind_a,
                kind_b=kind_b,
                count_a=len(rows_a),
                count_b=len(rows_b),
                only_a=only_a,
                only_b=only_b,
                overlap=overlap,
            )
        )
    return QuickDiffResult(
        resources=summaries,
        total_only_a=total_only_a,
        total_only_b=total_only_b,
        total_overlap=total_overlap,
    )
