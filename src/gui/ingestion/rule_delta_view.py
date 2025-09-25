"""Delta Viewer Backend (Milestone 7.10.18)

Provides a pure logic diff engine comparing existing persisted rows for a
resource against newly extracted rows (e.g. from single-file or batch preview)
to surface additions, removals, and per-field modifications prior to applying
ingestion rule changes.

Design Goals
------------
- Zero side effects; purely computes structured diff artifacts.
- Deterministic ordering for stable UI rendering & test assertions.
- Lightweight key inference heuristic when explicit key fields not provided.
- Clearly separates row identity (key tuple) from change payload detection.

Key Inference Heuristic
-----------------------
1. Explicit ``key_fields`` parameter when provided.
2. Field exactly named ``id`` (unique across both existing + new).
3. Any field ending with ``_id`` unique across combined rows (first match).
4. First combination of up to the first three alphabetical fields that yields
   uniqueness across combined rows.
5. Fallback: the full set of fields (sorted) – effectively treats the entire
   row as its own identity; changes then reduce to add/remove semantics if
   values differ anywhere.

Data Structures
---------------
- RowDelta: status ('added','removed','changed','unchanged') plus old/new rows and changed_fields map.
- DeltaResourceResult: per-resource diff result plus inferred key_fields used.
- DeltaViewResult: aggregate container across resources.

Future Extensions (later milestones)
------------------------------------
- Soft matching / fuzzy key alignment.
- Semantic key selection surfaced via UI.
- Per-field type-aware diff formatting (numbers, dates) with tolerance.
- Compact patch serialization for persistence / review.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict, Iterable, List, Mapping, Optional, Sequence, Tuple

__all__ = [
    "RowDelta",
    "DeltaResourceResult",
    "DeltaViewResult",
    "diff_resource",
    "generate_delta_view",
]


@dataclass
class RowDelta:
    key: Tuple[Any, ...]
    status: str  # added, removed, changed, unchanged
    old: Optional[Mapping[str, Any]]
    new: Optional[Mapping[str, Any]]
    changed_fields: Dict[str, Tuple[Any, Any]]

    def to_mapping(self) -> Mapping[str, Any]:  # pragma: no cover - trivial
        return {
            "key": self.key,
            "status": self.status,
            "old": dict(self.old) if self.old else None,
            "new": dict(self.new) if self.new else None,
            "changed_fields": {k: (v[0], v[1]) for k, v in self.changed_fields.items()},
        }


@dataclass
class DeltaResourceResult:
    resource: str
    key_fields: List[str]
    deltas: List[RowDelta]

    def summary_counts(self) -> Mapping[str, int]:  # pragma: no cover - trivial
        counts = {"added": 0, "removed": 0, "changed": 0, "unchanged": 0}
        for d in self.deltas:
            counts[d.status] += 1
        return counts

    def to_mapping(self) -> Mapping[str, Any]:  # pragma: no cover - trivial
        return {
            "resource": self.resource,
            "key_fields": list(self.key_fields),
            "deltas": [d.to_mapping() for d in self.deltas],
            "summary": self.summary_counts(),
        }


@dataclass
class DeltaViewResult:
    resources: List[DeltaResourceResult]

    def to_mapping(self) -> Mapping[str, Any]:  # pragma: no cover - trivial
        return {"resources": [r.to_mapping() for r in self.resources]}


def _infer_key_fields(existing: List[Mapping[str, Any]], new: List[Mapping[str, Any]]) -> List[str]:
    if not existing and not new:
        return []
    combined = existing + new
    all_fields = sorted({f for row in combined for f in row.keys()})
    # 1. Explicit 'id'
    if "id" in all_fields and _is_unique([row.get("id") for row in combined]):
        return ["id"]
    # 2. Any *_id single field
    for f in all_fields:
        if f.endswith("_id") and _is_unique([row.get(f) for row in combined]):
            return [f]
    # Helper: value appears at most once per side (allows one existing + one new for changed row)
    def side_unique(field: str) -> bool:
        seen_exist = set()
        for r in existing:
            v = r.get(field)
            if v in seen_exist:
                return False
            seen_exist.add(v)
        seen_new = set()
        for r in new:
            v = r.get(field)
            if v in seen_new:
                return False
            seen_new.add(v)
        return True

    # 3. Any single TEXTUAL field uniquely identifying rows per side (allows overlap across versions)
    textual_candidates: List[str] = []
    numeric_candidates: List[str] = []
    for f in all_fields:
        if side_unique(f):
            vals = [row.get(f) for row in combined]
            # classify heuristic: treat as numeric if all values are int/float
            if all(isinstance(v, (int, float)) or (isinstance(v, str) and v.strip().isdigit()) for v in vals if v is not None):
                numeric_candidates.append(f)
            else:
                textual_candidates.append(f)
    if textual_candidates:
        return [textual_candidates[0]]
    if numeric_candidates:
        return [numeric_candidates[0]]
    # 4. Increasing size combinations (first alphabetical prefix that is unique)
    for size in range(2, min(4, len(all_fields)) + 1):
        subset = all_fields[:size]
        if _is_unique([tuple(row.get(f) for f in subset) for row in combined]):
            return list(subset)
    # 5. Fallback: all fields
    return all_fields


def _is_unique(values: Iterable[Any]) -> bool:
    seen = set()
    for v in values:
        if v in seen:
            return False
        seen.add(v)
    return True


def _row_key(row: Mapping[str, Any], key_fields: Sequence[str]) -> Tuple[Any, ...]:
    return tuple(row.get(f) for f in key_fields)


def diff_resource(
    resource: str,
    existing_rows: List[Mapping[str, Any]],
    new_rows: List[Mapping[str, Any]],
    *,
    key_fields: Optional[Sequence[str]] = None,
) -> DeltaResourceResult:
    """Compute row-level delta for a single resource.

    Parameters
    ----------
    existing_rows : list[dict]
        Rows currently persisted (baseline).
    new_rows : list[dict]
        Newly extracted rows (candidate replacement set).
    key_fields : optional sequence of strings
        Explicit key column(s) to identify rows. When absent, applies inference.
    """
    if key_fields is None or not list(key_fields):
        inferred = _infer_key_fields(existing_rows, new_rows)
        key_fields = inferred
    else:
        key_fields = list(key_fields)

    existing_map: Dict[Tuple[Any, ...], Mapping[str, Any]] = {}
    for r in existing_rows:
        existing_map[_row_key(r, key_fields)] = r
    new_map: Dict[Tuple[Any, ...], Mapping[str, Any]] = {}
    for r in new_rows:
        new_map[_row_key(r, key_fields)] = r

    all_keys = sorted(set(existing_map.keys()) | set(new_map.keys()))
    deltas: List[RowDelta] = []
    for k in all_keys:
        old = existing_map.get(k)
        new = new_map.get(k)
        if old is None and new is not None:
            deltas.append(RowDelta(key=k, status="added", old=None, new=new, changed_fields={}))
        elif new is None and old is not None:
            deltas.append(RowDelta(key=k, status="removed", old=old, new=None, changed_fields={}))
        else:
            assert old is not None and new is not None  # for type checkers
            if old == new:
                deltas.append(RowDelta(key=k, status="unchanged", old=old, new=new, changed_fields={}))
            else:
                changed: Dict[str, Tuple[Any, Any]] = {}
                # union of field names
                fields = set(old.keys()) | set(new.keys())
                for f in sorted(fields):
                    ov = old.get(f)
                    nv = new.get(f)
                    if ov != nv:
                        changed[f] = (ov, nv)
                deltas.append(
                    RowDelta(
                        key=k,
                        status="changed",
                        old=old,
                        new=new,
                        changed_fields=changed,
                    )
                )
    return DeltaResourceResult(resource=resource, key_fields=list(key_fields), deltas=deltas)


def generate_delta_view(
    existing_by_resource: Mapping[str, List[Mapping[str, Any]]],
    new_by_resource: Mapping[str, List[Mapping[str, Any]]],
    *,
    key_fields_map: Optional[Mapping[str, Sequence[str]]] = None,
) -> DeltaViewResult:
    """Compute delta across multiple resources.

    Resources present only in one side are still surfaced (other side treated as empty).
    """
    all_resources = sorted(set(existing_by_resource.keys()) | set(new_by_resource.keys()))
    results: List[DeltaResourceResult] = []
    for r in all_resources:
        existing_rows = existing_by_resource.get(r, [])
        new_rows = new_by_resource.get(r, [])
        key_fields = None
        if key_fields_map and r in key_fields_map:
            key_fields = key_fields_map[r]
        results.append(
            diff_resource(
                r,
                list(existing_rows),
                list(new_rows),
                key_fields=key_fields,
            )
        )
    return DeltaViewResult(resources=results)
