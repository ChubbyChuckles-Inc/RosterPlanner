"""Synthetic example data row generator (Milestone 7.10.A10).

This module inspects a parsed :class:`RuleSet` and fabricates synthetic sample
rows that demonstrate how transform chains normalise representative raw inputs.
It is intentionally deterministic and dependency-free so it can be exercised in
unit tests and reused by both GUI and CLI tooling.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Any, Dict, Iterable, List, Sequence

from .rule_schema import FieldMapping, ListRule, RuleSet, TableRule, TransformSpec
from .rule_transforms import TransformExecutionError, apply_transform_chain

__all__ = ["ExampleRow", "generate_example_rows"]


@dataclass
class ExampleRow:
    """Synthetic example highlighting transform effects for a single field."""

    field: str
    raw: str
    normalized: str
    note: str = ""
    is_outlier: bool = False


def generate_example_rows(
    rule_set: RuleSet, *, max_samples_per_field: int = 3
) -> Dict[str, List[ExampleRow]]:
    """Generate synthetic example rows for each resource in *rule_set*.

    Parameters
    ----------
    rule_set:
        Parsed rule definition used to inspect resources, fields and transforms.
    max_samples_per_field:
        Upper bound per field to keep the output concise for UI rendering.

    Returns
    -------
    dict
        Mapping of resource name to a list of :class:`ExampleRow` instances.
    """

    results: Dict[str, List[ExampleRow]] = {}
    for name, resource in rule_set.resources.items():
        if isinstance(resource, ListRule):
            rows: List[ExampleRow] = []
            for field_name, mapping in resource.fields.items():
                rows.extend(
                    _build_rows_for_field(
                        field_name,
                        mapping,
                        allow_expressions=rule_set.allow_expressions,
                        limit=max_samples_per_field,
                    )
                )
            if rows:
                results[name] = rows
        elif isinstance(resource, TableRule):
            rows = [
                ExampleRow(
                    field=column,
                    raw="Sample cell",
                    normalized="Sample cell",
                    note="table column placeholder",
                    is_outlier=False,
                )
                for column in resource.columns
            ]
            if rows:
                results[name] = rows[: max_samples_per_field or len(rows)]
    return results


def _build_rows_for_field(
    field_name: str,
    mapping: FieldMapping,
    *,
    allow_expressions: bool,
    limit: int,
) -> List[ExampleRow]:
    """Generate :class:`ExampleRow` samples for a single field mapping."""

    transforms = mapping.transforms or []
    samples = _collect_sample_candidates(transforms)
    rows: List[ExampleRow] = []
    seen: set[str] = set()
    for raw in samples:
        if raw in seen:
            continue
        seen.add(raw)
        try:
            value = apply_transform_chain(raw, transforms, allow_expressions=allow_expressions)
            normalized = _format_value(value)
            outlier = _should_flag_outlier(raw, value, transforms)
            note = _note_for_transforms(transforms, outlier)
        except TransformExecutionError as exc:
            normalized = f"ERROR: {exc}"
            outlier = True
            note = "transform error"
        rows.append(
            ExampleRow(
                field=field_name,
                raw=raw,
                normalized=normalized,
                note=note,
                is_outlier=outlier,
            )
        )
        if 0 < limit <= len(rows):
            break
    return rows


def _collect_sample_candidates(transforms: Sequence[TransformSpec]) -> List[str]:
    """Return a deterministic list of raw samples based on transform kinds."""

    if not transforms:
        return ["Sample Value", "  Mixed Case Value  "]

    samples: List[str] = []
    kinds = {spec.kind for spec in transforms}
    if "to_number" in kinds:
        samples.extend(["1 234", "98,76", "N/A", " 42 "])
    if "parse_date" in kinds:
        formats = _formats_for_parse_date(transforms) or ["%Y-%m-%d"]
        seeds = [datetime(2024, 3, 12), datetime(2023, 11, 2)]
        for fmt in formats[:2]:  # limit to keep output predictable
            for seed in seeds:
                try:
                    samples.append(seed.strftime(fmt))
                except Exception:
                    continue
        samples.append("N/A")
    if "collapse_ws" in kinds:
        samples.append("Value   with\tmixed   whitespace")
    if "trim" in kinds:
        samples.append("  Trim me  ")
    if "expr" in kinds:
        samples.append("5")
    samples.append("  ")  # universal blank to surface None-handling behaviour
    return samples


def _formats_for_parse_date(transforms: Sequence[TransformSpec]) -> List[str]:
    """Extract strftime formats from the first parse_date transform encountered."""

    for spec in transforms:
        if spec.kind == "parse_date" and spec.formats:
            return list(spec.formats)
    return []


def _format_value(value: Any) -> str:
    """Normalise *value* to a human-friendly string representation."""

    if value is None:
        return "None"
    if isinstance(value, float):
        return f"{value:.6g}"
    return str(value)


def _should_flag_outlier(raw: str, value: Any, transforms: Sequence[TransformSpec]) -> bool:
    """Determine whether the transformed output should be highlighted as an outlier."""

    if value is None:
        return True
    raw_stripped = raw.strip()
    normalized = _format_value(value)
    if normalized != raw and normalized != raw_stripped:
        return True
    if any(spec.kind in {"to_number", "parse_date", "expr"} for spec in transforms):
        return normalized != raw_stripped
    return False


def _note_for_transforms(transforms: Sequence[TransformSpec], is_outlier: bool) -> str:
    """Describe the applied transform chain for display purposes."""

    if not transforms:
        return ""
    descriptor = " -> ".join(spec.kind for spec in transforms)
    if is_outlier:
        return f"transforms: {descriptor}"
    return f"transforms: {descriptor}"
