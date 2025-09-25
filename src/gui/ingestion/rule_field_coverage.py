"""Field Coverage Computation (Milestone 7.10.26)

Provides a pure-logic helper to analyze how well a ``RuleSet`` populates
its mapped (or implicit) database columns across a set of HTML documents.

Purpose
-------
Surface coverage ratios so the Ingestion Lab UI can render a *field
coverage heatmap* highlighting which target columns are consistently
populated, partially filled, or entirely missing for the current rules.

Scope (Initial Backend)
-----------------------
* Aggregates per-resource, per-field non-empty value counts.
* Optional mapping: resource -> field_name -> target_column. If omitted,
  field names themselves act as target column identifiers.
* Coverage = non_empty_count / total_rows for the resource (0 when no rows).
* Distinct count included for potential future uniqueness diagnostics.
* Missing columns list = mapped target columns whose non_empty_count == 0.

Out of Scope (Future Enhancements)
----------------------------------
* Integration with actual DB schema to include *unmapped* DB columns.
* Weighting by primary-key presence or downstream mapping usage.
* UI color scale & interactive filters (handled in subsequent tasks).

Design Notes
------------
* Reuses ``generate_parse_preview`` for extraction without transforms by
  default (fast). Optional `apply_transforms` flag mirrors other helpers.
* Keeps computation deterministic & side-effect free for easy unit tests.

Returns a ``FieldCoverageReport`` dataclass which the GUI layer can
serialize to JSON and feed into a table/heatmap widget.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict, List, Mapping, Optional

from .rule_schema import RuleSet, TableRule, ListRule
from .rule_parse_preview import generate_parse_preview

__all__ = [
    "FieldCoverageField",
    "FieldCoverageResource",
    "FieldCoverageReport",
    "compute_field_coverage",
]


@dataclass
class FieldCoverageField:
    """Per-field coverage statistics."""

    field: str
    target_column: str
    non_empty: int
    total_rows: int
    distinct: int

    @property
    def coverage_ratio(self) -> float:
        return (self.non_empty / self.total_rows) if self.total_rows else 0.0

    def to_mapping(self) -> Dict[str, Any]:  # pragma: no cover - trivial
        return {
            "field": self.field,
            "target_column": self.target_column,
            "non_empty": self.non_empty,
            "total_rows": self.total_rows,
            "distinct": self.distinct,
            "coverage_ratio": self.coverage_ratio,
        }


@dataclass
class FieldCoverageResource:
    resource: str
    kind: str
    fields: List[FieldCoverageField]

    def missing_columns(self) -> List[str]:
        return [f.target_column for f in self.fields if f.non_empty == 0]

    @property
    def average_coverage(self) -> float:
        if not self.fields:
            return 0.0
        return sum(f.coverage_ratio for f in self.fields) / len(self.fields)

    def to_mapping(self) -> Dict[str, Any]:  # pragma: no cover - trivial
        return {
            "resource": self.resource,
            "kind": self.kind,
            "fields": [f.to_mapping() for f in self.fields],
            "average_coverage": self.average_coverage,
            "missing_columns": self.missing_columns(),
        }


@dataclass
class FieldCoverageReport:
    resources: List[FieldCoverageResource]
    total_target_columns: int
    total_non_empty_cells: int
    total_possible_cells: int

    @property
    def overall_ratio(self) -> float:
        return (self.total_non_empty_cells / self.total_possible_cells) if self.total_possible_cells else 0.0

    def to_mapping(self) -> Dict[str, Any]:  # pragma: no cover - trivial
        return {
            "resources": [r.to_mapping() for r in self.resources],
            "total_target_columns": self.total_target_columns,
            "total_non_empty_cells": self.total_non_empty_cells,
            "total_possible_cells": self.total_possible_cells,
            "overall_ratio": self.overall_ratio,
        }


def compute_field_coverage(
    rule_set: RuleSet,
    html_by_file: Mapping[str, str],
    *,
    mapping: Optional[Mapping[str, Mapping[str, str]]] = None,
    apply_transforms: bool = False,
) -> FieldCoverageReport:
    """Compute field coverage statistics.

    Parameters
    ----------
    rule_set : RuleSet
        Active parsing rule set.
    html_by_file : Mapping[str, str]
        Mapping of file identifier -> HTML text.
    mapping : Optional mapping resource -> field_name -> target_column
        Declares DB target column names for each extracted field. If omitted,
        field names are used directly.
    apply_transforms : bool, default False
        When True, runs list field transform chains prior to coverage analysis.

    Returns
    -------
    FieldCoverageReport
        Structured coverage metrics.
    """
    # Aggregate all rows per resource across files.
    aggregated_rows: Dict[str, List[Dict[str, Any]]] = {r: [] for r in rule_set.resources.keys()}
    kinds: Dict[str, str] = {}

    for file_id, html in html_by_file.items():  # noqa: ARG001 - id not used yet
        preview = generate_parse_preview(
            rule_set, html, apply_transforms=apply_transforms, capture_performance=False
        )
        for res_name, rows in preview.flattened_tables.items():
            aggregated_rows.setdefault(res_name, []).extend(rows)
        # Capture kinds (table/list)
        for summary in preview.summaries:
            kinds[summary.resource] = summary.kind

    resources_out: List[FieldCoverageResource] = []
    total_target_columns = 0
    total_non_empty_cells = 0
    total_possible_cells = 0

    for res_name, rows in aggregated_rows.items():
        res_obj = rule_set.resources.get(res_name)
        if isinstance(res_obj, TableRule):
            field_names = list(res_obj.columns)
            kind = "table"
        elif isinstance(res_obj, ListRule):
            field_names = list(res_obj.fields.keys())
            kind = "list"
        else:  # pragma: no cover - unknown resource type
            continue

        # Determine mapping for this resource.
        res_mapping = mapping.get(res_name, {}) if mapping else {}
        coverage_fields: List[FieldCoverageField] = []
        row_count = len(rows)

        # Distinct sets cached per field
        distinct_cache: Dict[str, set] = {fn: set() for fn in field_names}
        non_empty_counts: Dict[str, int] = {fn: 0 for fn in field_names}

        for row in rows:
            for fn in field_names:
                val = row.get(fn)
                if val not in (None, ""):
                    non_empty_counts[fn] += 1
                    distinct_cache[fn].add(val)

        for fn in field_names:
            target_col = res_mapping.get(fn, fn)
            non_empty = non_empty_counts[fn]
            distinct = len(distinct_cache[fn])
            coverage_fields.append(
                FieldCoverageField(
                    field=fn,
                    target_column=target_col,
                    non_empty=non_empty,
                    total_rows=row_count,
                    distinct=distinct,
                )
            )
            total_target_columns += 1
            total_non_empty_cells += non_empty
            total_possible_cells += row_count

        resources_out.append(
            FieldCoverageResource(resource=res_name, kind=kind, fields=coverage_fields)
        )

    resources_out.sort(key=lambda r: r.resource)
    return FieldCoverageReport(
        resources=resources_out,
        total_target_columns=total_target_columns,
        total_non_empty_cells=total_non_empty_cells,
        total_possible_cells=total_possible_cells,
    )
