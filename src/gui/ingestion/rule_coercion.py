"""Data Type Coercion Preview (Milestone 7.10.15)

Takes sample extracted raw values (strings) for list & table resource fields
and runs the transform chains defined in the active RuleSet, producing a
summary of coercion success / failures per field along with exemplar failure
messages and a capped list of coerced preview values.

Scope:
 - Only list rule fields have transform chains. Table columns (currently) do
   not define transforms, so they are passed through as-is (string identity).
 - A failure is any raised TransformExecutionError or unexpected exception in
   a chain; subsequent transforms in that chain are skipped.
 - Coerced values are truncated to a maximum count per field for UI brevity.

Design Decisions:
 - Pure logic module (no DB / PyQt dependencies).
 - Structured result for easy JSON serialization.
 - Conservative error capture: first 5 distinct error messages stored.

Future Enhancements (not in this milestone):
 - Character-level diff for transformation changes.
 - Timing metrics per field.
 - Partial coercion for composite / structured transforms.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Dict, List, Mapping, Any, Iterable

from .rule_schema import RuleSet, ListRule, TableRule
from .rule_transforms import apply_transform_chain, TransformExecutionError

__all__ = [
    "FieldCoercionStats",
    "CoercionPreviewResult",
    "generate_coercion_preview",
]


@dataclass
class FieldCoercionStats:
    resource: str
    field: str  # field name (list) or column name (table)
    total: int
    success: int
    failures: int
    coerced_samples: List[Any] = field(default_factory=list)
    errors: List[str] = field(default_factory=list)  # distinct messages (capped)

    def to_mapping(self) -> Mapping[str, object]:  # pragma: no cover - trivial
        return {
            "resource": self.resource,
            "field": self.field,
            "total": self.total,
            "success": self.success,
            "failures": self.failures,
            "coerced_samples": list(self.coerced_samples),
            "errors": list(self.errors),
        }


@dataclass
class CoercionPreviewResult:
    stats: List[FieldCoercionStats]

    def to_mapping(self) -> Mapping[str, object]:  # pragma: no cover - trivial
        return {"stats": [s.to_mapping() for s in self.stats]}


RawSamples = Mapping[str, Mapping[str, List[str]]]

MAX_SAMPLES_PER_FIELD = 8
MAX_ERROR_MESSAGES = 5


def _coerce_list_field(
    resource: str,
    field: str,
    raw_values: Iterable[str],
    rule: ListRule,
    allow_expressions: bool,
) -> FieldCoercionStats:
    fmap = rule.fields.get(field)
    total = 0
    success = 0
    failures = 0
    coerced: List[Any] = []
    errors: List[str] = []
    if not fmap:
        return FieldCoercionStats(resource, field, 0, 0, 0)
    for raw in raw_values:
        total += 1
        try:
            val = apply_transform_chain(raw, fmap.transforms, allow_expressions=allow_expressions)
            success += 1
            if len(coerced) < MAX_SAMPLES_PER_FIELD:
                coerced.append(val)
        except TransformExecutionError as e:  # pragma: no cover - branch covered in tests
            failures += 1
            msg = str(e)
            if msg not in errors and len(errors) < MAX_ERROR_MESSAGES:
                errors.append(msg)
        except Exception as e:  # defensive
            failures += 1
            msg = f"unexpected: {e}"
            if msg not in errors and len(errors) < MAX_ERROR_MESSAGES:
                errors.append(msg)
    return FieldCoercionStats(resource, field, total, success, failures, coerced, errors)


def _coerce_table_column(
    resource: str, column: str, raw_values: Iterable[str]
) -> FieldCoercionStats:
    # No transforms yet; identity pass-through.
    total = 0
    success = 0
    coerced: List[str] = []
    for raw in raw_values:
        total += 1
        success += 1
        if len(coerced) < MAX_SAMPLES_PER_FIELD:
            coerced.append(raw)
    return FieldCoercionStats(resource, column, total, success, 0, coerced, [])


def generate_coercion_preview(rule_set: RuleSet, raw_samples: RawSamples) -> CoercionPreviewResult:
    """Generate coercion preview statistics.

    Parameters
    ----------
    rule_set : RuleSet
        Active rule set.
    raw_samples : Mapping[str, Mapping[str, List[str]]]
        Mapping resource -> field/column -> list of raw string values.
    """
    stats: List[FieldCoercionStats] = []
    for rname, res in rule_set.resources.items():
        per_field = raw_samples.get(rname, {})
        if isinstance(res, ListRule):
            for fname in sorted(res.fields.keys()):
                values = per_field.get(fname, [])
                stats.append(
                    _coerce_list_field(
                        rname, fname, values, res, rule_set.allow_expressions
                    )
                )
        elif isinstance(res, TableRule):
            for col in res.columns:
                values = per_field.get(col, [])
                stats.append(_coerce_table_column(rname, col, values))
        else:  # pragma: no cover - defensive future-proofing
            continue
    return CoercionPreviewResult(stats=stats)
