"""Data Quality Gates (Milestone 7.10.28)

Evaluates minimum non-null ratio thresholds over extracted resource fields
using the existing field coverage computation.

Gate Configuration
------------------
Accepted input mapping forms (merged together if both used):
1. Flat mapping: {"resource.field": 0.85, ...}
2. Nested mapping: {"resource": {"field": 0.85, ...}, ...}
Values represent min required (non_empty / total_rows) ratio. Ratio is 0 for a
field when there are zero rows (treated as failing unless threshold also 0).

Returns a ``QualityGateReport`` containing individual results plus summary
counts for the Ingestion Lab UI.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, List, Mapping, Any

from .rule_schema import RuleSet
from .rule_field_coverage import compute_field_coverage

__all__ = [
    "QualityGateResult",
    "QualityGateReport",
    "evaluate_quality_gates",
]


@dataclass
class QualityGateResult:
    resource: str
    field: str
    threshold: float
    ratio: float
    passed: bool

    def to_mapping(self) -> Dict[str, Any]:  # pragma: no cover - trivial
        return {
            "resource": self.resource,
            "field": self.field,
            "threshold": self.threshold,
            "ratio": self.ratio,
            "passed": self.passed,
        }


@dataclass
class QualityGateReport:
    results: List[QualityGateResult]

    @property
    def passed(self) -> bool:
        return all(r.passed for r in self.results)

    @property
    def failed_count(self) -> int:
        return sum(1 for r in self.results if not r.passed)

    def to_mapping(self) -> Dict[str, Any]:  # pragma: no cover - trivial
        return {
            "results": [r.to_mapping() for r in self.results],
            "passed": self.passed,
            "failed_count": self.failed_count,
        }


def _normalize_gate_config(raw: Mapping[str, Any]) -> Dict[str, float]:
    out: Dict[str, float] = {}
    for key, value in raw.items():
        if isinstance(value, (int, float)):
            out[key] = float(value)
        elif isinstance(value, Mapping):
            # nested form
            for f, thresh in value.items():
                if isinstance(thresh, (int, float)):
                    out[f"{key}.{f}"] = float(thresh)
        # ignore unsupported types silently (UI can warn later)
    return out


def evaluate_quality_gates(
    rule_set: RuleSet,
    html_by_file: Mapping[str, str],
    gate_config: Mapping[str, Any],
) -> QualityGateReport:
    coverage = compute_field_coverage(rule_set, html_by_file)
    # Build quick lookup: (resource, field) -> ratio
    ratios: Dict[tuple[str, str], float] = {}
    for res in coverage.resources:
        for f in res.fields:
            ratios[(res.resource, f.field)] = f.coverage_ratio
    flat = _normalize_gate_config(gate_config)
    results: List[QualityGateResult] = []
    for dotted, threshold in sorted(flat.items()):
        if "." not in dotted:
            continue
        resource, field = dotted.split(".", 1)
        ratio = ratios.get((resource, field), 0.0)
        passed = ratio >= threshold
        results.append(
            QualityGateResult(
                resource=resource, field=field, threshold=threshold, ratio=ratio, passed=passed
            )
        )
    return QualityGateReport(results=results)
