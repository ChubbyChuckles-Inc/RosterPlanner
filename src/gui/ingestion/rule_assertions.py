"""Rule Assertions Evaluation (Milestone 7.10.23)

Provides a lightweight assertion mechanism allowing the Ingestion Lab to
validate expected extracted values during preview runs. Assertions are
declarative dictionaries (JSON-friendly) with the following minimal schema:

    {
        "resource": "ranking",          # required, resource name in RuleSet
        "field": "team",               # required, column (table) or field (list)
        "expect": "LTTV",              # required, expected string value (post-transform)
        "index": 0,                     # optional, default 0 (row/item index)
        "op": "eq"                     # optional, 'eq' (default) or 'contains'
    }

Transform & expression application is delegated to the existing parse preview
logic (``generate_parse_preview``) invoked by callers prior to evaluation.

Security: Assertions are pure data. No expression evaluation is performed here.

Future Extensions (documented for roadmap alignment):
 - Support numeric comparisons (gt/lt/ge/le)
 - Regex matching
 - Negation flag
 - Aggregation assertions (row count >= N)

This module intentionally keeps dependencies minimal and is side-effect free.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import List, Mapping, Any, Sequence, Dict

from .rule_schema import RuleSet
from .rule_parse_preview import ParsePreview

__all__ = [
    "AssertionSpec",
    "AssertionResult",
    "evaluate_assertions",
]


@dataclass
class AssertionSpec:
    """Declarative assertion specification.

    Attributes
    ----------
    resource: str
        Resource name defined in the active RuleSet.
    field: str
        Column (table) or field (list) name to check.
    expect: str
        Expected value (string comparison after transforms).
    index: int
        Row index (0-based) within the flattened resource rows. Defaults to 0.
    op: str
        Comparison operator: 'eq' (default) or 'contains'. Unknown values treated as 'eq'.
    """

    resource: str
    field: str
    expect: str
    index: int = 0
    op: str = "eq"

    @staticmethod
    def from_mapping(data: Mapping[str, Any]) -> "AssertionSpec":
        try:
            resource = str(data["resource"]).strip()
            field = str(data["field"]).strip()
            expect = str(data["expect"])  # allow empty string expectation
        except Exception as e:  # pragma: no cover - defensive
            raise ValueError(f"Invalid assertion mapping (missing required keys): {data!r}") from e
        if not resource or not field:
            raise ValueError("Assertion requires non-empty 'resource' and 'field'")
        idx = int(data.get("index", 0) or 0)
        op = str(data.get("op", "eq") or "eq").lower()
        if op not in {"eq", "contains"}:
            op = "eq"
        return AssertionSpec(resource=resource, field=field, expect=expect, index=idx, op=op)


@dataclass
class AssertionResult:
    """Result of a single assertion evaluation."""

    spec: AssertionSpec
    passed: bool
    actual: Any
    message: str

    def to_mapping(self) -> Mapping[str, Any]:  # pragma: no cover - trivial
        return {
            "resource": self.spec.resource,
            "field": self.spec.field,
            "index": self.spec.index,
            "op": self.spec.op,
            "expect": self.spec.expect,
            "actual": self.actual,
            "passed": self.passed,
            "message": self.message,
        }


def evaluate_assertions(
    rule_set: RuleSet,
    preview: ParsePreview,
    assertions: Sequence[AssertionSpec],
) -> List[AssertionResult]:
    """Evaluate assertions against an existing parse preview.

    Parameters
    ----------
    rule_set : RuleSet
        Active rule set (used for existence validation).
    preview : ParsePreview
        Generated preview data containing flattened tables.
    assertions : Sequence[AssertionSpec]
        Assertions to evaluate.

    Returns
    -------
    list[AssertionResult]
        Results for each assertion (order preserved).
    """
    results: List[AssertionResult] = []
    for spec in assertions:
        # Resource existence
        if spec.resource not in preview.flattened_tables:
            results.append(
                AssertionResult(
                    spec=spec,
                    passed=False,
                    actual=None,
                    message="resource not present in preview",
                )
            )
            continue
        rows = preview.flattened_tables.get(spec.resource, [])
        if spec.index < 0 or spec.index >= len(rows):
            results.append(
                AssertionResult(
                    spec=spec,
                    passed=False,
                    actual=None,
                    message="index out of range",
                )
            )
            continue
        row = rows[spec.index]
        actual = row.get(spec.field)
        if actual is None:
            results.append(
                AssertionResult(
                    spec=spec, passed=False, actual=None, message="field missing in row"
                )
            )
            continue
        # Normalize to string for comparison (preserve original actual value reference for reporting)
        actual_str = str(actual)
        exp_str = spec.expect
        if spec.op == "contains":
            passed = exp_str in actual_str
        else:  # eq
            passed = actual_str == exp_str
        results.append(
            AssertionResult(
                spec=spec,
                passed=passed,
                actual=actual,
                message="ok" if passed else f"expected {exp_str!r} got {actual_str!r}",
            )
        )
    return results
