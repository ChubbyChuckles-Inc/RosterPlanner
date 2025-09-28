"""Field dependency tracing utilities (Milestone 7.10.A13).

The goal of the trace is to explain, for a selected derived field, which
upstream fields contribute to its value and what transform chains are applied
along the way. The module intentionally keeps PyQt6 out of scope so the logic
is unit-testable and can be reused by different viewers (CLI, GUI, tests).
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Dict, List, Mapping, Optional, Sequence, Set, Tuple
import ast
import json

from .rule_schema import FieldMapping, ListRule, RuleError, RuleSet, TableRule, TransformSpec

__all__ = [
    "TraceTransform",
    "FieldTraceStep",
    "TraceBuildError",
    "list_derived_fields",
    "build_field_trace",
]


@dataclass(frozen=True)
class TraceTransform:
    """Descriptor for a single transform in the dependency trace."""

    kind: str
    code: Optional[str] = None
    formats: Sequence[str] | None = None
    source: str = "inline"  # either "inline" or "macro"
    macro: Optional[str] = None

    def describe(self) -> str:
        extra: List[str] = []
        if self.macro:
            extra.append(f"macro {self.macro}")
        if self.code:
            extra.append(f"code={self.code}")
        if self.formats:
            extra.append("formats=" + ",".join(self.formats))
        meta = f" ({'; '.join(extra)})" if extra else ""
        return f"{self.kind}{meta}"


@dataclass(frozen=True)
class FieldTraceStep:
    """Single row in the dependency trace."""

    name: str
    type: str
    depth: int
    resource: Optional[str] = None
    selector: Optional[str] = None
    expression: Optional[str] = None
    transforms: Tuple[TraceTransform, ...] = field(default_factory=tuple)
    note: Optional[str] = None


class TraceBuildError(ValueError):
    """Raised when the trace cannot be constructed (e.g., cycles)."""


def _ensure_mapping(payload: str | Mapping[str, object]) -> Mapping[str, object]:
    if isinstance(payload, str):
        try:
            data = json.loads(payload or "{}")
        except Exception as exc:  # pragma: no cover - parse guard
            raise TraceBuildError(f"Cannot parse rules text: {exc}") from exc
        if not isinstance(data, Mapping):  # pragma: no cover - defensive
            raise TraceBuildError("Rules root must be a mapping object")
        return data
    if not isinstance(payload, Mapping):
        raise TraceBuildError("Rules payload must be mapping or JSON string")
    return payload


def list_derived_fields(payload: str | Mapping[str, object]) -> List[str]:
    mapping = _ensure_mapping(payload)
    derived = mapping.get("derived")
    if not isinstance(derived, Mapping):
        return []
    names = [
        name for name, expr in derived.items() if isinstance(name, str) and isinstance(expr, str)
    ]
    return sorted(set(names))


def _extract_names_from_expr(expr: str) -> Set[str]:
    try:
        tree = ast.parse(expr, mode="eval")
    except Exception:
        return set()
    names: Set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Name):
            names.add(node.id)
    return names


def _collect_resource_indexes(rule_set: RuleSet) -> Tuple[
    Dict[str, List[Tuple[str, FieldMapping]]],
    Dict[str, List[str]],
]:
    list_fields: Dict[str, List[Tuple[str, FieldMapping]]] = {}
    table_columns: Dict[str, List[str]] = {}
    for rname, resource in rule_set.resources.items():
        if isinstance(resource, ListRule):
            for fname, fmap in resource.fields.items():
                list_fields.setdefault(fname, []).append((rname, fmap))
        elif isinstance(resource, TableRule):
            for col in resource.columns:
                table_columns.setdefault(col, []).append(rname)
    return list_fields, table_columns


def _clone_transform(spec: TransformSpec, *, source: str, macro: Optional[str]) -> TraceTransform:
    formats = tuple(spec.formats) if spec.formats else None
    return TraceTransform(
        kind=spec.kind, code=spec.code, formats=formats, source=source, macro=macro
    )


def _gather_transforms(
    fmap: FieldMapping,
    transform_macros: Mapping[str, Sequence[TransformSpec]],
    known_fields: Set[str],
) -> Tuple[Tuple[TraceTransform, ...], Set[str]]:
    transforms: List[TraceTransform] = []
    expr_refs: Set[str] = set()
    for macro_name in fmap.macro_refs:
        chain = transform_macros.get(macro_name, ())
        for spec in chain:
            transforms.append(_clone_transform(spec, source="macro", macro=macro_name))
            if spec.kind == "expr" and spec.code:
                expr_refs |= _extract_names_from_expr(spec.code)
    for spec in fmap.inline_transforms:
        transforms.append(_clone_transform(spec, source="inline", macro=None))
        if spec.kind == "expr" and spec.code:
            expr_refs |= _extract_names_from_expr(spec.code)
    filtered_refs = {name for name in expr_refs if name in known_fields}
    return tuple(transforms), filtered_refs


def build_field_trace(
    payload: str | Mapping[str, object],
    target_field: str,
) -> List[FieldTraceStep]:
    mapping = _ensure_mapping(payload)
    if not isinstance(target_field, str) or not target_field:
        raise TraceBuildError("target_field must be a non-empty string")
    derived = mapping.get("derived")
    if not isinstance(derived, Mapping) or target_field not in derived:
        raise TraceBuildError(f"Derived field '{target_field}' not found")

    try:
        ruleset = RuleSet.from_mapping(mapping)  # type: ignore[arg-type]
    except RuleError as exc:  # pragma: no cover - schema validation handled elsewhere
        raise TraceBuildError(f"Cannot parse ruleset: {exc}") from exc

    list_fields, table_columns = _collect_resource_indexes(ruleset)
    transform_macros = getattr(ruleset, "transform_macros", {})  # type: ignore[attr-defined]
    derived_names = {name for name in derived.keys() if isinstance(name, str)}
    known_fields = set(list_fields.keys()) | set(table_columns.keys()) | derived_names

    steps: List[FieldTraceStep] = []
    visited: Set[str] = set()
    stack: List[str] = []

    def add_step(step: FieldTraceStep) -> None:
        steps.append(step)

    def trace(name: str, depth: int) -> None:
        if name in stack:
            cycle = " -> ".join(stack + [name])
            raise TraceBuildError(f"Cycle detected: {cycle}")
        already_seen = name in visited
        stack.append(name)
        try:
            if name in derived and isinstance(derived[name], str):
                expr = derived[name]
                note = "already detailed above" if already_seen else None
                add_step(
                    FieldTraceStep(
                        name=name,
                        type="derived",
                        depth=depth,
                        expression=expr,
                        note=note,
                    )
                )
                if already_seen:
                    return
                visited.add(name)
                refs = sorted(_extract_names_from_expr(expr) & known_fields)
                for ref in refs:
                    trace(ref, depth + 1)
                return
            matches = False
            if name in list_fields:
                for resource, fmap in list_fields[name]:
                    note = "already detailed above" if already_seen else None
                    transforms, expr_refs = _gather_transforms(fmap, transform_macros, known_fields)
                    add_step(
                        FieldTraceStep(
                            name=name,
                            type="list_field",
                            depth=depth,
                            resource=resource,
                            selector=fmap.selector,
                            transforms=transforms,
                            note=note,
                        )
                    )
                    if already_seen:
                        matches = True
                        continue
                    visited.add(name)
                    matches = True
                    for ref in sorted(expr_refs):
                        trace(ref, depth + 1)
            if name in table_columns:
                for resource in table_columns[name]:
                    note = "already detailed above" if already_seen else None
                    add_step(
                        FieldTraceStep(
                            name=name,
                            type="table_column",
                            depth=depth,
                            resource=resource,
                            note=note,
                        )
                    )
                    matches = True
                    if not already_seen:
                        visited.add(name)
            if not matches:
                add_step(
                    FieldTraceStep(
                        name=name,
                        type="unknown",
                        depth=depth,
                        note="No matching resource field",
                    )
                )
        finally:
            stack.pop()

    trace(target_field, depth=0)
    return steps
