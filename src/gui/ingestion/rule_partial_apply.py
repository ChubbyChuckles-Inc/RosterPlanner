"""Partial Apply Mode (Milestone 7.10.21)

Allows users to apply only a selected subset of extracted resources from a
``RuleSet`` into a temporary sandbox SQLite database for iterative refinement.

Design Goals
------------
* Non-destructive: always uses an in-memory SQLite connection the caller owns.
* Deterministic & testable: pure function style; no global state mutation.
* Reuses existing preview extraction logic (``generate_parse_preview``) and the
  sandbox schema builder (``build_sandbox_schema`` / ``apply_sandbox_schema``).
* Minimal scope: no diffing vs live DB, no provenance tagging yet (later tasks).

API Overview
------------
``partial_apply(rule_set, html_by_file, resources, *, apply_transforms=False)``
    Returns a ``PartialApplyResult`` capturing per-table inserted row counts
    and any structured parse errors encountered.

Insertion Strategy
------------------
Each resource is mapped to a sandbox table named ``sandbox_<resource>``. For
table rules, the flattened row dict is inserted with missing columns defaulting
to empty string. For list rules, field mappings become columns. Only resources
explicitly listed in ``resources`` are processed; others are ignored entirely
even if present in the rule set (keeping operation fast for iterative trials).

Error Handling
--------------
Structured warnings/errors from the underlying parse previews are aggregated
with file enrichment. Insertion failures for a specific row (unlikely under
SQLite's permissive typing) are recorded as error entries but do not abort the
overall operation.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, List, Mapping, Sequence, Any
import sqlite3

from .rule_schema import RuleSet, TableRule, ListRule
from .rule_parse_preview import generate_parse_preview
from .rule_sandbox import build_sandbox_schema, apply_sandbox_schema

__all__ = [
    "PartialApplyResult",
    "partial_apply",
]


@dataclass
class PartialApplyResult:
    inserted_rows: Dict[str, int]  # sandbox_<resource> -> count
    errors: List[Mapping[str, Any]]
    tables: List[str]

    def to_mapping(self) -> Mapping[str, Any]:  # pragma: no cover - trivial
        return {
            "inserted_rows": dict(self.inserted_rows),
            "errors": list(self.errors),
            "tables": list(self.tables),
        }


def partial_apply(
    rule_set: RuleSet,
    html_by_file: Mapping[str, str],
    resources: Sequence[str],
    *,
    apply_transforms: bool = False,
) -> PartialApplyResult:
    """Apply a subset of resources to a fresh sandbox DB and return insertion stats.

    Parameters
    ----------
    rule_set : RuleSet
        Active rule set.
    html_by_file : Mapping[str, str]
        Mapping of logical file id -> raw HTML content.
    resources : Sequence[str]
        Resource names (as defined in rule_set.resources) to include in the partial apply.
    apply_transforms : bool, default False
        Forwarded to underlying preview generation for list rule field transforms.
    """
    # Filter to existing resources only; silently ignore unknown names (caller may pass stale list)
    selected = [r for r in resources if r in rule_set.resources]
    # Build a trimmed RuleSet containing only selected resources to keep extraction fast
    trimmed = RuleSet(
        resources={r: rule_set.resources[r] for r in selected},
        allow_expressions=rule_set.allow_expressions,
    )
    # Build sandbox schema (type inference & table naming handled inside)
    schema = build_sandbox_schema(trimmed)
    conn = apply_sandbox_schema(schema)
    inserted_counts: Dict[str, int] = {}
    aggregated_errors: List[Mapping[str, Any]] = []

    for file_id, html in html_by_file.items():
        preview = generate_parse_preview(
            trimmed, html, apply_transforms=apply_transforms, capture_performance=False
        )
        # Aggregate errors with file enrichment
        for err in preview.errors:
            e = dict(err)
            e["file"] = file_id
            aggregated_errors.append(e)
        # Insert rows for each selected resource
        for rname in selected:
            table_name = f"sandbox_{rname}"
            rows = preview.flattened_tables.get(rname, [])
            if not rows:
                continue
            # Prepare dynamic column list from first row keys to keep insert stable
            # (Schema builder already created columns for mapping entries; if a key was
            # absent due to empty data, SQLite will still accept it once present.)
            columns = sorted(rows[0].keys())
            placeholders = ",".join(["?"] * len(columns))
            sql = f"INSERT INTO {table_name} ({', '.join(columns)}) VALUES ({placeholders})"
            cur = conn.cursor()
            for row in rows:
                try:
                    values = [row.get(c, "") for c in columns]
                    cur.execute(sql, values)
                    inserted_counts[table_name] = inserted_counts.get(table_name, 0) + 1
                except Exception as e:  # pragma: no cover - defensive; unlikely
                    aggregated_errors.append(
                        {
                            "resource": rname,
                            "kind": trimmed.resource_kind(rname),
                            "message": f"Row insert failed: {e}",
                            "severity": "error",
                            "file": file_id,
                        }
                    )
            conn.commit()

    return PartialApplyResult(
        inserted_rows=inserted_counts,
        errors=aggregated_errors,
        tables=[t.name for t in schema.tables],
    )
