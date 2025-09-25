"""Rule Documentation Generator (Milestone 7.10.10)

Provides small, self‑contained helper functions to build human‑readable
documentation snippets for the ingestion rule schema. The Ingestion Lab UI
can use these snippets as rich tooltips / side panels without embedding
knowledge of the rule dataclasses.

Design Goals
------------
* Pure logic (no PyQt imports) – easy to unit test.
* Deterministic output for snapshot/unit tests.
* Light formatting in Markdown so it can be rendered as plain text or
  converted to rich text (e.g. using a Markdown viewer in a tooltip popover).
* Avoid expensive DOM inspection here (validation already handled elsewhere).

Public API
----------
generate_global_docs(rule_set) -> str
    Full schema overview + transform kinds + resource index.
generate_resource_docs(resource_name, rule_set) -> str
    Focused documentation for a single resource (structure, inherited data,
    field/column listing, transform chains if present).

Future Extensions (later milestones may add):
* Attribute extraction / regex capture examples.
* Live selector evaluation stats (hook into validation report cache).
* Hyperlinks / anchors for larger help panel.
"""

from __future__ import annotations

from typing import List, Dict

from .rule_schema import RuleSet, TableRule, ListRule, TransformSpec

__all__ = ["generate_global_docs", "generate_resource_docs"]


def _format_transform(t: TransformSpec) -> str:
    if t.kind == "parse_date":  # include formats context
        fmts = ", ".join(t.formats or [])
        return f"parse_date(formats=[{fmts}])"
    if t.kind == "expr":
        # Show a trimmed preview of the code (avoid leaking large text)
        preview = t.code.strip().replace("\n", " ") if t.code else ""
        if len(preview) > 40:
            preview = preview[:37] + "..."
        return f"expr: {preview}"
    return t.kind


def _resource_index(rule_set: RuleSet) -> str:
    lines = ["### Resources", "", "| Name | Kind | Extends |", "|------|------|---------|"]
    for name in rule_set.list_resources():
        res = rule_set.resources[name]
        if isinstance(res, TableRule):
            parent = res.extends or ""
            lines.append(f"| {name} | table | {parent} |")
        elif isinstance(res, ListRule):
            parent = res.extends or ""
            lines.append(f"| {name} | list | {parent} |")
    lines.append("")
    return "\n".join(lines)


def _transform_section(rule_set: RuleSet) -> str:
    lines = [
        "### Transform Kinds",
        "",
        "* trim – strip leading/trailing whitespace",
        "* collapse_ws – collapse internal whitespace to single spaces",
        "* to_number – parse integer/float (comma→dot normalization)",
        "* parse_date – parse date string using supplied strptime formats",
    ]
    if rule_set.allow_expressions:
        lines.append(
            "* expr – safe Python expression (value variable available; restricted builtins)"
        )
    else:
        lines.append("* expr – (disabled; enable by setting allow_expressions: true)")
    lines.append("")
    return "\n".join(lines)


def generate_global_docs(rule_set: RuleSet) -> str:
    """Generate a global schema overview in Markdown."""
    parts: List[str] = [
        "# Rule Schema Documentation",
        "",
        "This document summarizes the currently loaded rule set.",
        "",
        f"Schema Version: **{rule_set.version}**  | Expressions Enabled: **{rule_set.allow_expressions}**",
        "",
        _resource_index(rule_set),
        _transform_section(rule_set),
        "### Inheritance",
        "",
        "Resources may declare `extends: parent_name` to inherit selector / columns (tables) or selector / item_selector / fields (lists). Child definitions override parent entries with the same field name.",
        "",
        "Use the per-resource tooltip for detailed field / column information.",
    ]
    return "\n".join(parts)


def generate_resource_docs(resource_name: str, rule_set: RuleSet) -> str:
    """Generate focused documentation for a specific resource.

    Includes structure, inheritance chain (if any), and field/column transform
    summaries. Returns Markdown text.
    """
    if resource_name not in rule_set.resources:
        raise ValueError(f"Unknown resource '{resource_name}'")
    res = rule_set.resources[resource_name]
    lines: List[str] = [f"## Resource: {resource_name}", ""]
    if isinstance(res, TableRule):
        lines.append("Kind: **table**")
        lines.append(f"Selector: `{res.selector}`")
        if res.extends:
            lines.append(f"Extends: `{res.extends}`")
        lines.append("")
        lines.append("### Columns")
        for col in res.columns:
            lines.append(f"- {col}")
    elif isinstance(res, ListRule):
        lines.append("Kind: **list**")
        lines.append(f"Root Selector: `{res.selector}`")
        lines.append(f"Item Selector: `{res.item_selector}`")
        if res.extends:
            lines.append(f"Extends: `{res.extends}`")
        lines.append("")
        lines.append("### Fields")
        for fname, fmap in sorted(res.fields.items()):
            if fmap.transforms:
                chain = " | ".join(_format_transform(t) for t in fmap.transforms)
                lines.append(f"- **{fname}**: `{fmap.selector}`  (transforms: {chain})")
            else:
                lines.append(f"- **{fname}**: `{fmap.selector}`")
    else:  # pragma: no cover - defensive
        lines.append(f"Unsupported resource type {type(res).__name__}")
    lines.append("")
    lines.append("_Generated by rule_docs.generate_resource_docs_")
    return "\n".join(lines)
