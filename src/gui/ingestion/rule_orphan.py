"""Orphan Field Detector (Milestone 7.10.27)

Identifies extracted fields declared in the active RuleSet that are not
mapped to any target column (user-provided mapping block). Provides a
lightweight suggestion string for remediation.

Current Scope
-------------
* Pure logic function: compute_orphan_fields(rule_set, mapping).
* Mapping format: Mapping[str, Mapping[str, str]] where outer key is
  resource name and inner key is field name -> target column. For table
  rules, column names function as both field & target; omission means orphan.
* Suggestions are simple textual hints (future enhancement: structured actions).

Out of Scope
------------
* Automatic pruning or schema mutation.
* Deep analysis of downstream usage (handled by later dependency graph tasks).

Testing Strategy
----------------
Provide a focused unit test that constructs a rule set with an omitted field
in the mapping and asserts the orphan list contains that field.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import List, Mapping, Dict

from .rule_schema import RuleSet, TableRule, ListRule

__all__ = ["OrphanField", "compute_orphan_fields"]


@dataclass
class OrphanField:
    resource: str
    field: str
    suggestion: str

    def to_mapping(self) -> Dict[str, str]:  # pragma: no cover - trivial
        return {"resource": self.resource, "field": self.field, "suggestion": self.suggestion}


def compute_orphan_fields(
    rule_set: RuleSet, mapping: Mapping[str, Mapping[str, str]] | None
) -> List[OrphanField]:
    mapping = mapping or {}
    out: List[OrphanField] = []
    for rname, res in rule_set.resources.items():
        if isinstance(res, TableRule):
            fields = list(res.columns)
        elif isinstance(res, ListRule):
            fields = list(res.fields.keys())
        else:  # pragma: no cover
            continue
        declared = set(fields)
        mapped_fields = set(mapping.get(rname, {}).keys())
        orphans = sorted(declared - mapped_fields)
        for f in orphans:
            out.append(
                OrphanField(
                    resource=rname,
                    field=f,
                    suggestion=f"Add mapping for '{f}' in resource '{rname}' or remove field if obsolete",
                )
            )
    return out
