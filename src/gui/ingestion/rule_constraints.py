"""Constraint Simulation (Milestone 7.10.14)

Provides a lightweight, pure-logic engine to surface potential uniqueness and
foreign key issues prior to committing a schema migration. This operates on
sample (preview) rows supplied by the caller (later milestones will generate
those rows from extraction previews / sandbox execution).

Scope (initial):
 - Uniqueness heuristic: any column exactly named 'id' or ending with '_id'
   in a table resource is treated as a candidate unique key. Duplicate
   non-null values are reported.
 - Foreign key heuristic: for any column ending with '_id', attempt to infer
   a referenced table by stripping the suffix. If a table of that name exists
   (singular/plural tolerant by exact match), values in the referencing column
   not present in the target table's 'id' column are reported as orphans.

Design Rationale:
 - Keep heuristics simple & deterministic; UI can later allow user overrides.
 - Decouple from DB layer so unit tests operate entirely in memory.
 - Provide structured issues for display (severity classification can be
   added later without breaking consumers).

Future Extensions (not in this milestone):
 - Composite key inference.
 - User-declared unique / FK constraints overriding heuristics.
 - NULL handling policies (currently NULLs ignored for uniqueness & FK).
 - Severity levels / quick-fix suggestions.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, List, Mapping, Optional, Iterable, Any

from .rule_schema import RuleSet, TableRule

__all__ = [
    "ConstraintIssue",
    "ConstraintSimulationResult",
    "simulate_constraints",
]


@dataclass
class ConstraintIssue:
    kind: str  # 'unique_violation' | 'fk_orphan'
    table: str
    column: str
    value: Any
    row_indexes: List[int]
    message: str

    def to_mapping(self) -> Mapping[str, object]:  # pragma: no cover - trivial
        return {
            "kind": self.kind,
            "table": self.table,
            "column": self.column,
            "value": self.value,
            "row_indexes": list(self.row_indexes),
            "message": self.message,
        }


@dataclass
class ConstraintSimulationResult:
    issues: List[ConstraintIssue]

    def has_errors(self) -> bool:
        return bool(self.issues)

    def to_mapping(self) -> Mapping[str, object]:  # pragma: no cover - trivial
        return {"issues": [i.to_mapping() for i in self.issues]}


SampleRows = Mapping[str, List[Mapping[str, Any]]]


def _candidate_unique_columns(rule_set: RuleSet) -> Dict[str, List[str]]:
    """Return heuristic candidate unique columns per table resource."""
    result: Dict[str, List[str]] = {}
    for name, res in rule_set.resources.items():
        if isinstance(res, TableRule):
            cols = [c for c in res.columns if c == "id" or c.endswith("_id")]
            if cols:
                result[name] = cols
    return result


def _infer_referenced_table(column: str, table_names: Iterable[str]) -> Optional[str]:
    if not column.endswith("_id"):
        return None
    base = column[:-3]  # strip _id
    # Exact match heuristic
    if base in table_names:
        return base
    # Simple plural heuristic (add/remove trailing 's')
    if base.endswith("s") and base[:-1] in table_names:
        return base[:-1]
    if (base + "s") in table_names:
        return base + "s"
    return None


def simulate_constraints(rule_set: RuleSet, samples: SampleRows) -> ConstraintSimulationResult:
    """Simulate constraint issues using sample rows.

    Parameters
    ----------
    rule_set : RuleSet
        Active rule schema (only table resources are considered for now).
    samples : Mapping[str, List[Mapping[str, Any]]]
        Sample rows keyed by resource name; missing resources are ignored.
    """
    issues: List[ConstraintIssue] = []
    table_names = [n for n, r in rule_set.resources.items() if isinstance(r, TableRule)]
    unique_candidates = _candidate_unique_columns(rule_set)

    # Build id sets for FK checks
    id_values: Dict[str, set] = {}
    for tname in table_names:
        rows = samples.get(tname, [])
        id_set = set()
        for r in rows:
            if "id" in r and r["id"] is not None:
                id_set.add(r["id"])
        id_values[tname] = id_set

    # Uniqueness violations
    for tname, columns in unique_candidates.items():
        rows = samples.get(tname, [])
        for col in columns:
            seen: Dict[Any, List[int]] = {}
            for idx, row in enumerate(rows):
                val = row.get(col)
                if val is None:
                    continue
                seen.setdefault(val, []).append(idx)
            for val, idxs in seen.items():
                if len(idxs) > 1:
                    issues.append(
                        ConstraintIssue(
                            kind="unique_violation",
                            table=tname,
                            column=col,
                            value=val,
                            row_indexes=idxs,
                            message=f"Duplicate value {val!r} in column '{col}' of table '{tname}'",
                        )
                    )

    # Foreign key orphans
    for tname in table_names:
        rows = samples.get(tname, [])
        for col in [c for c in unique_candidates.get(tname, []) if c.endswith("_id")]:
            ref_table = _infer_referenced_table(col, table_names)
            if not ref_table:
                continue
            ref_ids = id_values.get(ref_table, set())
            for idx, row in enumerate(rows):
                val = row.get(col)
                if val is None:
                    continue
                if val not in ref_ids:
                    issues.append(
                        ConstraintIssue(
                            kind="fk_orphan",
                            table=tname,
                            column=col,
                            value=val,
                            row_indexes=[idx],
                            message=f"Value {val!r} in '{tname}.{col}' has no parent in '{ref_table}.id'",
                        )
                    )
    return ConstraintSimulationResult(issues=issues)
