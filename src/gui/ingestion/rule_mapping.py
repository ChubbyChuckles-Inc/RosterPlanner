"""Rule -> Target Schema Mapping Model (Milestone 7.10.11)

Backend logic that will power the forthcoming visual mapping grid (7.10.11).
It converts a ``RuleSet`` into a set of mapping entries capturing:
 - resource name
 - field / column name (source)
 - proposed target column name (default: identical; future: user overrides)
 - inferred logical type (STRING | NUMBER | DATE | UNKNOWN)
 - transform summary (chain kinds)

The GUI layer can display these entries and allow the user to adjust target
column names or override inferred types before generating DB migration previews
in later milestones (7.10.12+).

Inference Heuristics (initial, conservative):
 - If any transform in chain has kind == 'to_number' -> NUMBER
 - Else if any transform has kind == 'parse_date' -> DATE
 - Else -> STRING (unless chain empty and no transforms -> STRING)
 - Expression transforms do not influence type directly (user may override later)

Table rules already declare column order; we treat each column as STRING by
default (later we could infer when transforms at a field-level adapter appear).

Pure logic: no DB or PyQt dependencies, enabling unit tests.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import List, Dict, Mapping, Iterable

from .rule_schema import RuleSet, ListRule, TableRule, TransformSpec

__all__ = [
    "FieldType",
    "MappingEntry",
    "build_mapping_entries",
    "group_by_resource",
]


class FieldType(str, Enum):
    STRING = "string"
    NUMBER = "number"
    DATE = "date"
    UNKNOWN = "unknown"


@dataclass
class MappingEntry:
    resource: str
    source_name: str  # field name (list rule) or column name (table rule)
    target_column: str  # proposed DB column name
    inferred_type: FieldType
    transforms: List[str] = field(default_factory=list)
    is_table: bool = False

    def to_mapping(self) -> Mapping[str, object]:  # JSON friendly for UI
        return {
            "resource": self.resource,
            "source_name": self.source_name,
            "target_column": self.target_column,
            "inferred_type": self.inferred_type.value,
            "transforms": list(self.transforms),
            "is_table": self.is_table,
        }


def _infer_type_from_transforms(transforms: Iterable[TransformSpec]) -> FieldType:
    kinds = [t.kind for t in transforms]
    if "to_number" in kinds:
        return FieldType.NUMBER
    if "parse_date" in kinds:
        return FieldType.DATE
    # expressions do not automatically change inferred type
    return FieldType.STRING


def build_mapping_entries(rule_set: RuleSet) -> List[MappingEntry]:
    """Produce mapping entries for all resources in the rule set."""
    entries: List[MappingEntry] = []
    for rname, res in rule_set.resources.items():
        if isinstance(res, ListRule):
            for fname, fmap in res.fields.items():
                inferred = _infer_type_from_transforms(fmap.transforms)
                entries.append(
                    MappingEntry(
                        resource=rname,
                        source_name=fname,
                        target_column=fname,  # default identical
                        inferred_type=inferred,
                        transforms=[t.kind for t in fmap.transforms],
                        is_table=False,
                    )
                )
        elif isinstance(res, TableRule):
            for col in res.columns:
                entries.append(
                    MappingEntry(
                        resource=rname,
                        source_name=col,
                        target_column=col,
                        inferred_type=FieldType.STRING,  # no transform context
                        transforms=[],
                        is_table=True,
                    )
                )
        else:  # pragma: no cover - defensive
            continue
    return entries


def group_by_resource(entries: List[MappingEntry]) -> Dict[str, List[MappingEntry]]:
    grouped: Dict[str, List[MappingEntry]] = {}
    for e in entries:
        grouped.setdefault(e.resource, []).append(e)
    # stable ordering: table/list natural order preserved (already appended sequentially)
    return grouped
