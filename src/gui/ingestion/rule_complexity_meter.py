"""Rule complexity heuristic scoring utilities (Milestone 7.10.A14).

The scoring model provides a quick, qualitative signal for how difficult a
rule set may be to maintain. The meter considers three primary factors for
each field:

* Selector specificity depth (long, highly specific selectors are harder to
  keep stable when source HTML drifts).
* Transform chain length (longer normalization pipelines are more fragile).
* Inheritance depth (deep chains of `extends` relationships increase the
  mental model required to reason about a resource).

The resulting per-field score is a simple sum of these heuristics. The overall
rule score is derived from the average and peak field scores and mapped to a
low / moderate / high guidance level that can be surfaced in the UI as a
color-coded badge.

Design goals:
    - Pure-Python utility (no Qt dependency) so it can be unit-tested in
      isolation and reused across CLI, GUI, or reporting workflows.
    - Conservative heuristics: the meter should never block workflows; it only
      provides guidance.
    - Extensible: thresholds and scoring factors are expressed as module-level
      constants so future milestones can refine the model.
"""

from __future__ import annotations

from dataclasses import dataclass
import json
import re
from typing import Any, Dict, Iterable, List, Mapping, Optional, Sequence

from gui.ingestion.rule_schema import (
    FieldMapping,
    ListRule,
    RuleError,
    RuleSet,
    TableRule,
    TransformSpec,
)

__all__ = [
    "RuleComplexityError",
    "FieldComplexity",
    "RuleComplexityReport",
    "compute_rule_complexity",
]

# ---------------------------------------------------------------------------
# Configuration constants

# Thresholds chosen empirically: selector depth greater than ~6 and transform
# chains longer than ~6 tend to hide brittle selectors or over-normalization.
_LOW_THRESHOLD = 6
_MODERATE_THRESHOLD = 12

_BASE_BADGE = "neutral"
_BADGE_FOR_GRADE = {
    "Low": "low",
    "Moderate": "moderate",
    "High": "high",
}

_GUIDANCE_BY_GRADE = {
    "Low": "Looking good – selectors are concise and transform chains stay under the recommended limit.",
    "Moderate": "Consider simplifying selectors or consolidating transforms to keep the rules easier to reason about.",
    "High": "Complex rule set detected. Review selectors and transform chains to reduce fragility before expanding further.",
}

_SELECTOR_SPLIT_RE = re.compile(r"\s+|[>+~]")
_SELECTOR_ATTR_RE = re.compile(r"[#.][A-Za-z0-9_-]+|\[[^\]]+\]")


class RuleComplexityError(ValueError):
    """Raised when rule complexity analysis cannot be completed."""


@dataclass(frozen=True)
class FieldComplexity:
    """Complexity metrics for a single field or table column."""

    resource: str
    field: str
    kind: str  # "list_field" or "table_column"
    selector_depth: int
    transform_count: int
    inheritance_depth: int
    expr_penalty: int
    score: int

    def to_mapping(self) -> Dict[str, Any]:  # pragma: no cover - simple serialization
        return {
            "resource": self.resource,
            "field": self.field,
            "kind": self.kind,
            "selector_depth": self.selector_depth,
            "transform_count": self.transform_count,
            "inheritance_depth": self.inheritance_depth,
            "expr_penalty": self.expr_penalty,
            "score": self.score,
        }


@dataclass(frozen=True)
class RuleComplexityReport:
    """Aggregate complexity outcome for an entire rule set."""

    overall_score: float
    max_score: int
    grade: str
    badge: str
    selector_avg: float
    transform_avg: float
    inheritance_avg: float
    field_count: int
    guidance: str
    details: Sequence[FieldComplexity]

    def to_mapping(self) -> Dict[str, Any]:  # pragma: no cover - simple serialization
        return {
            "overall_score": self.overall_score,
            "max_score": self.max_score,
            "grade": self.grade,
            "badge": self.badge,
            "selector_avg": self.selector_avg,
            "transform_avg": self.transform_avg,
            "inheritance_avg": self.inheritance_avg,
            "field_count": self.field_count,
            "guidance": self.guidance,
            "details": [d.to_mapping() for d in self.details],
        }


# ---------------------------------------------------------------------------
# Internal helpers


def _ensure_mapping(payload: Mapping[str, Any] | str) -> Mapping[str, Any]:
    if isinstance(payload, Mapping):
        return payload
    if isinstance(payload, str):
        try:
            data = json.loads(payload or "{}")
        except Exception as exc:  # pragma: no cover - defensive
            raise RuleComplexityError(f"Cannot parse rules text: {exc}") from exc
        if not isinstance(data, Mapping):
            raise RuleComplexityError("Rules root must be a JSON object")
        return data
    raise RuleComplexityError("Rules payload must be a mapping or JSON string")


def _estimate_selector_depth(selector: str) -> int:
    if not selector:
        return 0
    best = 0
    for part in selector.split(","):
        segment = part.strip()
        if not segment:
            continue
        structural_tokens = [tok for tok in _SELECTOR_SPLIT_RE.split(segment) if tok]
        attr_tokens = _SELECTOR_ATTR_RE.findall(segment)
        depth = len(structural_tokens) + len(attr_tokens)
        if depth > best:
            best = depth
    return best or 1


def _inheritance_depths(rule_set: RuleSet) -> Dict[str, int]:
    depths: Dict[str, int] = {}

    def depth_for(name: str, stack: Optional[List[str]] = None) -> int:
        if name in depths:
            return depths[name]
        stack = stack or []
        if name in stack:  # pragma: no cover - defensive; schema should prevent cycles
            return len(stack)
        resource = rule_set.resources.get(name)
        if resource is None:
            depths[name] = 0
            return 0
        parent = getattr(resource, "extends", None)
        if not parent:
            depths[name] = 0
            return 0
        stack.append(name)
        value = 1 + depth_for(parent, stack)
        stack.pop()
        depths[name] = value
        return value

    for resource_name in rule_set.resources:
        depth_for(resource_name)
    return depths


def _macro_chain(
    macros: Mapping[str, Sequence[TransformSpec]], name: str
) -> Sequence[TransformSpec]:
    chain = macros.get(name)
    if not isinstance(chain, Sequence):  # pragma: no cover - defensive
        return ()
    return chain


def _collect_transform_specs(
    field_mapping: FieldMapping,
    macros: Mapping[str, Sequence[TransformSpec]],
) -> tuple[List[TransformSpec], List[TransformSpec]]:
    macro_specs: List[TransformSpec] = []
    for macro_name in field_mapping.macro_refs:
        macro_specs.extend(list(_macro_chain(macros, macro_name)))
    if field_mapping.inline_transforms:
        inline_specs = list(field_mapping.inline_transforms)
    elif field_mapping.macro_refs:
        # No explicit inline transforms; everything comes from macros
        inline_specs = []
    else:
        inline_specs = list(field_mapping.transforms)
    return macro_specs, inline_specs


def _transform_stats(
    field_mapping: FieldMapping,
    macros: Mapping[str, Sequence[TransformSpec]],
) -> tuple[int, int]:
    macro_specs, inline_specs = _collect_transform_specs(field_mapping, macros)
    expr_penalty = sum(
        1 for spec in macro_specs + inline_specs if getattr(spec, "kind", "") == "expr"
    )
    count = len(macro_specs) + len(inline_specs)
    return count, expr_penalty


def _field_complexity_for_list(
    resource_name: str,
    rule: ListRule,
    fmap_items: Iterable[tuple[str, FieldMapping]],
    inheritance_depth: int,
    macros: Mapping[str, Sequence[Any]],
) -> List[FieldComplexity]:
    results: List[FieldComplexity] = []
    resource_selector_depth = _estimate_selector_depth(rule.selector)
    item_selector_depth = _estimate_selector_depth(rule.item_selector)
    for field_name, fmap in fmap_items:
        selector_depth = (
            resource_selector_depth + item_selector_depth + _estimate_selector_depth(fmap.selector)
        )
        transform_count, expr_penalty = _transform_stats(fmap, macros)
        score = selector_depth + transform_count + inheritance_depth + expr_penalty
        results.append(
            FieldComplexity(
                resource=resource_name,
                field=field_name,
                kind="list_field",
                selector_depth=selector_depth,
                transform_count=transform_count,
                inheritance_depth=inheritance_depth,
                expr_penalty=expr_penalty,
                score=score,
            )
        )
    return results


def _field_complexity_for_table(
    resource_name: str,
    rule: TableRule,
    inheritance_depth: int,
) -> List[FieldComplexity]:
    selector_depth = _estimate_selector_depth(rule.selector)
    results: List[FieldComplexity] = []
    for column in rule.columns:
        score = selector_depth + inheritance_depth
        results.append(
            FieldComplexity(
                resource=resource_name,
                field=column,
                kind="table_column",
                selector_depth=selector_depth,
                transform_count=0,
                inheritance_depth=inheritance_depth,
                expr_penalty=0,
                score=score,
            )
        )
    return results


def _grade_from_score(max_score: int) -> str:
    if max_score <= _LOW_THRESHOLD:
        return "Low"
    if max_score <= _MODERATE_THRESHOLD:
        return "Moderate"
    return "High"


# ---------------------------------------------------------------------------
# Public API


def compute_rule_complexity(payload: Mapping[str, Any] | str) -> RuleComplexityReport:
    """Compute heuristic complexity metrics for a rule set.

    Parameters
    ----------
    payload:
        Either a mapping already parsed from JSON/YAML or a JSON string.

    Returns
    -------
    RuleComplexityReport
        Aggregate metrics including per-field detail for further diagnostics.

    Raises
    ------
    RuleComplexityError
        If the payload cannot be parsed into a valid :class:`RuleSet`.
    """

    mapping = _ensure_mapping(payload)
    try:
        rule_set = RuleSet.from_mapping(mapping)  # type: ignore[arg-type]
    except RuleError as exc:  # pragma: no cover - schema validation already unit-tested
        raise RuleComplexityError(f"Invalid rule set: {exc}") from exc

    inheritance_map = _inheritance_depths(rule_set)
    macros = rule_set.transform_macros or {}

    field_entries: List[FieldComplexity] = []
    for resource_name, resource in rule_set.resources.items():
        inherit_depth = inheritance_map.get(resource_name, 0)
        if isinstance(resource, ListRule):
            entries = _field_complexity_for_list(
                resource_name,
                resource,
                resource.fields.items(),
                inherit_depth,
                macros,
            )
            field_entries.extend(entries)
        elif isinstance(resource, TableRule):
            field_entries.extend(
                _field_complexity_for_table(resource_name, resource, inherit_depth)
            )
        else:  # pragma: no cover - defensive for future resource types
            continue

    if not field_entries:
        return RuleComplexityReport(
            overall_score=0.0,
            max_score=0,
            grade="Low",
            badge=_BASE_BADGE,
            selector_avg=0.0,
            transform_avg=0.0,
            inheritance_avg=0.0,
            field_count=0,
            guidance=_GUIDANCE_BY_GRADE["Low"],
            details=tuple(),
        )

    total_selector = sum(entry.selector_depth for entry in field_entries)
    total_transforms = sum(entry.transform_count for entry in field_entries)
    total_inheritance = sum(entry.inheritance_depth for entry in field_entries)
    total_scores = sum(entry.score for entry in field_entries)
    count = len(field_entries)

    max_score = max(entry.score for entry in field_entries)
    grade = _grade_from_score(max_score)
    badge = _BADGE_FOR_GRADE.get(grade, _BASE_BADGE)
    guidance = _GUIDANCE_BY_GRADE.get(grade, _GUIDANCE_BY_GRADE["Low"])

    report = RuleComplexityReport(
        overall_score=round(total_scores / count, 2),
        max_score=max_score,
        grade=grade,
        badge=badge,
        selector_avg=round(total_selector / count, 2),
        transform_avg=round(total_transforms / count, 2),
        inheritance_avg=round(total_inheritance / count, 2),
        field_count=count,
        guidance=guidance,
        details=tuple(field_entries),
    )
    return report
