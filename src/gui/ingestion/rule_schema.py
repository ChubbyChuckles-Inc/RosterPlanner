"""Ingestion Rule Schema (Milestone 7.10.6).

Defines a declarative, serializable schema (YAML / JSON friendly) for HTML
extraction rules. The initial scope intentionally focuses on the core
building blocks needed by forthcoming milestones (validation, mapping,
preview execution) while keeping the surface area minimal and testable.

Design Goals:
 - Pure data container layer (no PyQt imports) to keep logic testable.
 - Explicit types & validation with clear error messages.
 - Forward compatible: additional fields (transforms, inheritance) will be
   added in later milestones (7.10.7+), guarded by VERSION bumping.
 - Minimal normalization so authors can write concise YAML.

Serialization:
 - `from_mapping` / `to_mapping` allow round-tripping plain dict payloads
   (after YAML or JSON parse) without coupling to a specific backend.

Versioning Strategy:
 - RULESET_VERSION constant increments on breaking structural changes.
 - Consumers embed version in persisted documents to enable migrations.

Example (YAML):

    version: 1
    resources:
      ranking_table:
        selector: 'table.ranking'
        kind: table
        columns: [team, points, diff]
      team_roster:
        selector: 'div.roster'
        kind: list
        item_selector: 'div.player'
        fields:
          name: '.name'
          live_pz: '.lpz'

"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Dict, List, Mapping, Any, Optional, Union, Set

RULESET_VERSION = 1

__all__ = [
    "RULESET_VERSION",
    "RuleError",
    "TransformSpec",
    "FieldMapping",
    "TableRule",
    "ListRule",
    "RuleResource",
    "RuleSet",
]


class RuleError(ValueError):
    """Raised for invalid rule declarations."""


@dataclass
class TransformSpec:
    """Represents a single value transformation applied in a chain.

    Supported kinds (initial 7.10.7 scope):
    - trim: strip leading/trailing whitespace
    - collapse_ws: collapse internal whitespace to single spaces
    - to_number: parse int/float (locale-neutral, comma -> dot normalization)
    - parse_date: parse date string into ISO date; requires 'formats' list
    - expr: (optional) safe Python expression executed with 'value' in locals;
            only allowed when RuleSet.allow_expressions is True. This is a
            provisional power-user feature and will be sandboxed further in
            later milestones (security hardening tasks).

    Serialization forms accepted in rule documents:
      - Simple string ("trim", "collapse_ws", "to_number")
      - Mapping with 'kind' (and optional params):
          {kind: parse_date, formats: ['%d.%m.%Y', '%Y-%m-%d']}
          {kind: expr, code: 'value.replace(\",\", \'\.\')'}
    """

    kind: str
    formats: Optional[List[str]] = None  # for parse_date
    code: Optional[str] = None  # for expr

    def to_mapping(self) -> Union[str, Mapping[str, Any]]:
        if self.kind in {"trim", "collapse_ws", "to_number"} and not self.formats and not self.code:
            # Serialize simple transforms as bare strings for conciseness
            return self.kind
        data: Dict[str, Any] = {"kind": self.kind}
        if self.formats:
            data["formats"] = list(self.formats)
        if self.code is not None:
            data["code"] = self.code
        return data

    @staticmethod
    def parse(obj: Any, *, allow_expr: bool) -> "TransformSpec":
        if isinstance(obj, str):
            kind = obj.strip()
            if not kind:
                raise RuleError("Transform string cannot be empty")
            if kind not in {"trim", "collapse_ws", "to_number"}:
                raise RuleError(f"Unsupported simple transform: {kind}")
            return TransformSpec(kind=kind)
        if isinstance(obj, Mapping):
            kind = obj.get("kind")
            if kind not in {"trim", "collapse_ws", "to_number", "parse_date", "expr"}:
                raise RuleError(f"Unsupported transform kind: {kind!r}")
            if kind == "expr":
                if not allow_expr:
                    raise RuleError("Expression transforms disabled (allow_expressions=False)")
                code = obj.get("code")
                if not isinstance(code, str) or not code.strip():
                    raise RuleError("Expression transform requires non-empty 'code'")
                return TransformSpec(kind="expr", code=code)
            if kind == "parse_date":
                fmts = obj.get("formats")
                if (
                    not isinstance(fmts, list)
                    or not fmts
                    or any(not isinstance(f, str) or not f for f in fmts)
                ):
                    raise RuleError("parse_date transform requires non-empty list 'formats'")
                return TransformSpec(kind="parse_date", formats=fmts)
            # Remaining simple kinds may appear as mapping without params
            return TransformSpec(kind=kind)
        raise RuleError(f"Unsupported transform spec value: {obj!r}")


@dataclass
class FieldMapping:
    """Mapping of extracted field name -> CSS selector + optional transforms."""

    selector: str
    transforms: List[TransformSpec] = field(default_factory=list)

    def to_mapping(self) -> Mapping[str, Any]:  # noqa: D401 - simple
        data: Dict[str, Any] = {"selector": self.selector}
        if self.transforms:
            data["transforms"] = [t.to_mapping() for t in self.transforms]
        return data

    @staticmethod
    def from_value(value: Any, *, allow_expressions: bool) -> "FieldMapping":
        if isinstance(value, str):
            if not value.strip():
                raise RuleError("Field selector cannot be empty")
            return FieldMapping(selector=value.strip())
        if isinstance(value, Mapping):
            sel = value.get("selector")
            if not isinstance(sel, str) or not sel.strip():
                raise RuleError("Field mapping requires non-empty 'selector'")
            raw_transforms = value.get("transforms", [])
            transforms: List[TransformSpec] = []
            if raw_transforms:
                if not isinstance(raw_transforms, list):
                    raise RuleError("Field 'transforms' must be a list")
                for idx, tval in enumerate(raw_transforms):
                    try:
                        transforms.append(TransformSpec.parse(tval, allow_expr=allow_expressions))
                    except RuleError as e:  # augment path
                        raise RuleError(f"Invalid transform at index {idx}: {e}") from e
            return FieldMapping(selector=sel.strip(), transforms=transforms)
        raise RuleError(f"Unsupported field mapping value: {value!r}")


@dataclass
class TableRule:
    """Represents a table extraction (structured rows & declared columns)."""

    selector: str
    columns: List[str]
    extends: Optional[str] = None  # parent resource name (table)

    def __post_init__(self) -> None:
        if not self.selector or not self.selector.strip():
            raise RuleError("TableRule.selector cannot be empty")
        if not self.columns:
            raise RuleError("TableRule.columns cannot be empty")
        if any(not c or not isinstance(c, str) for c in self.columns):
            raise RuleError("All TableRule.columns entries must be non-empty strings")
        seen = set()
        dups = [c for c in self.columns if c in seen or seen.add(c)]  # type: ignore[arg-type]
        if dups:
            raise RuleError(f"Duplicate column names: {', '.join(sorted(set(dups)))}")

    def to_mapping(self) -> Mapping[str, Any]:
        data: Dict[str, Any] = {"kind": "table", "selector": self.selector, "columns": list(self.columns)}
        if self.extends:
            data["extends"] = self.extends
        return data


@dataclass
class ListRule:
    """Represents a list extraction where each item becomes a record.

    fields maps output field name -> FieldMapping (CSS selector relative to the item node).
    """

    selector: str
    item_selector: str
    fields: Dict[str, FieldMapping]
    extends: Optional[str] = None  # parent resource name (list)

    def __post_init__(self) -> None:
        if not self.selector.strip():
            raise RuleError("ListRule.selector cannot be empty")
        if not self.item_selector.strip():
            raise RuleError("ListRule.item_selector cannot be empty")
        if not self.fields:
            raise RuleError("ListRule.fields cannot be empty")
        for name, fm in self.fields.items():
            if not name or not isinstance(name, str):
                raise RuleError("Field names must be non-empty strings")
            if not isinstance(fm, FieldMapping):
                raise RuleError("ListRule.fields values must be FieldMapping instances")

    def to_mapping(self) -> Mapping[str, Any]:
        data: Dict[str, Any] = {
            "kind": "list",
            "selector": self.selector,
            "item_selector": self.item_selector,
            "fields": {k: v.to_mapping() for k, v in self.fields.items()},
        }
        if self.extends:
            data["extends"] = self.extends
        return data


RuleResource = Union[TableRule, ListRule]


@dataclass
class RuleSet:
    """Container of named extraction resources.

    Attributes
    ----------
    version: int
        Schema version (for forward migration when new features land).
    resources: Dict[str, RuleResource]
        Mapping of logical resource name -> rule definition.
    """

    resources: Dict[str, RuleResource] = field(default_factory=dict)
    version: int = RULESET_VERSION
    allow_expressions: bool = False  # security gate for expr transforms

    # ------------------------------------------------------------------
    # Construction / Serialization
    @staticmethod
    def from_mapping(payload: Mapping[str, Any]) -> "RuleSet":
        if not isinstance(payload, Mapping):
            raise RuleError("RuleSet payload must be a mapping/dict")
        version = payload.get("version", RULESET_VERSION)
        if not isinstance(version, int):
            raise RuleError("RuleSet 'version' must be int")
        allow_expr = payload.get("allow_expressions", False)
        if not isinstance(allow_expr, bool):
            raise RuleError("RuleSet 'allow_expressions' must be a bool")
        raw_resources = payload.get("resources", {})
        if not isinstance(raw_resources, Mapping):
            raise RuleError("RuleSet 'resources' must be a mapping")

        # Store raw specs for second-pass inheritance resolution
        raw_specs: Dict[str, Mapping[str, Any]] = {}
        for name, spec in raw_resources.items():
            if not isinstance(name, str) or not name.strip():
                raise RuleError("Resource names must be non-empty strings")
            if not isinstance(spec, Mapping):
                raise RuleError(f"Resource '{name}' must be a mapping")
            raw_specs[name] = spec

        building: Set[str] = set()
        built: Dict[str, RuleResource] = {}

        def build_resource(rname: str) -> RuleResource:
            if rname in built:
                return built[rname]
            if rname in building:
                raise RuleError(f"Cyclic inheritance detected at resource '{rname}'")
            if rname not in raw_specs:
                raise RuleError(f"Unknown resource referenced in extends: '{rname}'")
            building.add(rname)
            spec = raw_specs[rname]
            kind = spec.get("kind")
            parent_name = spec.get("extends")
            parent: RuleResource | None = None
            if parent_name:
                if not isinstance(parent_name, str) or not parent_name.strip():
                    raise RuleError(f"Resource '{rname}' has invalid 'extends' value")
                parent = build_resource(parent_name)

            if kind == "table":
                selector = spec.get("selector")
                columns = spec.get("columns")
                if parent is not None and not isinstance(parent, TableRule):
                    raise RuleError(f"Resource '{rname}' extends non-table parent '{parent_name}'")
                if columns is None and isinstance(parent, TableRule):
                    columns = list(parent.columns)
                if not isinstance(columns, list):
                    raise RuleError(f"Resource '{rname}' table 'columns' must be a list (after inheritance)")
                rule = TableRule(selector=selector, columns=columns, extends=parent_name)  # type: ignore[arg-type]
            elif kind == "list":
                selector = spec.get("selector")
                item_sel = spec.get("item_selector")
                raw_fields = spec.get("fields") or {}
                if not isinstance(raw_fields, Mapping):
                    raise RuleError(f"Resource '{rname}' list 'fields' must be a mapping")
                # Start with parent fields (shallow copy)
                merged_fields: Dict[str, FieldMapping] = {}
                if parent is not None:
                    if not isinstance(parent, ListRule):
                        raise RuleError(f"Resource '{rname}' extends non-list parent '{parent_name}'")
                    # copy parent fields
                    for fname, fval in parent.fields.items():
                        merged_fields[fname] = FieldMapping(selector=fval.selector, transforms=list(fval.transforms))
                    if selector is None:
                        selector = parent.selector
                    if item_sel is None:
                        item_sel = parent.item_selector
                # Apply overrides / additions
                for fname, fval in raw_fields.items():
                    merged_fields[fname] = FieldMapping.from_value(fval, allow_expressions=allow_expr)
                rule = ListRule(selector=selector, item_selector=item_sel, fields=merged_fields, extends=parent_name)  # type: ignore[arg-type]
            else:
                raise RuleError(f"Resource '{rname}' missing or unsupported kind: {kind!r}")
            built[rname] = rule
            building.remove(rname)
            return rule

        for rname in list(raw_specs.keys()):
            build_resource(rname)

        return RuleSet(resources=built, version=version, allow_expressions=allow_expr)

    def to_mapping(self) -> Mapping[str, Any]:
        data = {
            "version": self.version,
            "resources": {k: v.to_mapping() for k, v in self.resources.items()},
        }
        if self.allow_expressions:
            data["allow_expressions"] = True
        return data

    # Convenience -------------------------------------------------------
    def ensure_resource(self, name: str) -> RuleResource:
        if name not in self.resources:
            raise RuleError(f"Unknown resource: {name}")
        return self.resources[name]

    def list_resources(self) -> List[str]:  # noqa: D401 - simple alias
        return sorted(self.resources.keys())

    def resource_kind(self, name: str) -> str:
        res = self.ensure_resource(name)
        if isinstance(res, TableRule):
            return "table"
        if isinstance(res, ListRule):
            return "list"
        raise RuleError(f"Unsupported resource type for {name}")
