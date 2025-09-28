"""Utilities for extracting and updating YAML fragments from ingestion rules.

This module keeps all parsing and placeholder generation logic free of Qt so it
can be unit-tested in isolation. The inline YAML editor dialog (Milestone
7.10.A15) uses these helpers to prefill resource snippets, compute ghost
placeholders, and merge edited fragments back into the full rules document.
"""

from __future__ import annotations

from dataclasses import dataclass
import json
from typing import Any, Dict, Iterable, List, Mapping, MutableMapping, Tuple

import yaml

# ---------------------------------------------------------------------------
# Errors & data models


class FragmentError(ValueError):
    """Raised when a YAML fragment cannot be parsed or applied."""


@dataclass(frozen=True)
class PlaceholderSpec:
    """Represents a recommended key/value placeholder for ghost text."""

    path: Tuple[str, ...]
    display: str
    snippet: str


# ---------------------------------------------------------------------------
# Public helpers


def load_rules(text: str) -> Dict[str, Any]:
    """Parse the full rules JSON payload."""

    try:
        return json.loads(text or "{}")
    except json.JSONDecodeError as exc:  # pragma: no cover - validated upstream
        raise FragmentError(f"Failed to parse rules JSON: {exc}") from exc


def resource_fragment_yaml(
    resource_name: str, resource_spec: Mapping[str, Any], *, include_name: bool = True
) -> str:
    """Render a single resource as YAML."""

    fragment: Mapping[str, Any]
    if include_name:
        fragment = {resource_name: resource_spec}
    else:
        fragment = resource_spec
    return yaml.safe_dump(fragment, sort_keys=False, default_flow_style=False, indent=2)


def clean_fragment_text(fragment: str) -> str:
    """Strip ghost marker lines (prefixed with ``#?``)."""

    lines = []
    for line in fragment.splitlines():
        if line.lstrip().startswith("#?"):
            continue
        lines.append(line.rstrip())
    return "\n".join(lines).strip() + "\n"


def parse_fragment_yaml(fragment: str, fallback_name: str) -> Tuple[str, Dict[str, Any]]:
    """Parse YAML fragment into (resource_name, resource_spec)."""

    cleaned = clean_fragment_text(fragment)
    if not cleaned.strip():
        raise FragmentError("Fragment is empty")
    try:
        obj = yaml.safe_load(cleaned)
    except yaml.YAMLError as exc:
        raise FragmentError(f"Invalid YAML fragment: {exc}") from exc
    if obj is None:
        raise FragmentError("Fragment did not contain any data")
    if not isinstance(obj, Mapping):
        raise FragmentError("Fragment must be a mapping")
    if len(obj) == 1 and all(isinstance(v, Mapping) for v in obj.values()):
        resource_name, spec = next(iter(obj.items()))
        return str(resource_name), dict(spec)
    # Treat payload as direct spec for the existing name
    if not isinstance(obj, MutableMapping):
        spec = dict(obj)  # type: ignore[arg-type]
    else:
        spec = dict(obj)
    return fallback_name, spec


def apply_fragment(
    rules: Mapping[str, Any], target_name: str, fragment_text: str
) -> Dict[str, Any]:
    """Merge an edited YAML fragment back into the full rules mapping."""

    if "resources" not in rules or not isinstance(rules["resources"], Mapping):
        raise FragmentError("Rules payload missing 'resources' mapping")
    new_name, spec = parse_fragment_yaml(fragment_text, target_name)
    updated: Dict[str, Any] = json.loads(json.dumps(rules))
    resources = updated.setdefault("resources", {})
    if target_name in resources and new_name != target_name:
        resources.pop(target_name)
    resources[new_name] = spec
    return updated


def generate_placeholders(resource_spec: Mapping[str, Any]) -> List[PlaceholderSpec]:
    """Determine recommended placeholder entries for missing keys."""

    placeholders: List[PlaceholderSpec] = []
    kind = str(resource_spec.get("kind", "")).lower()

    def add_placeholder(path: Iterable[str], display: str, snippet: str) -> None:
        placeholders.append(PlaceholderSpec(tuple(path), display, snippet))

    if kind == "table":
        if "selector" not in resource_spec:
            add_placeholder(("selector",), 'selector: ""', 'selector: ""\n')
        if "columns" not in resource_spec:
            add_placeholder(("columns",), "columns: []", "columns:\n  - column_1\n")
        if "extends" not in resource_spec:
            add_placeholder(("extends",), "extends: base_resource", "extends: base_resource\n")
    elif kind == "list":
        if "selector" not in resource_spec:
            add_placeholder(("selector",), 'selector: ""', 'selector: ""\n')
        if "item_selector" not in resource_spec:
            add_placeholder(("item_selector",), 'item_selector: ""', 'item_selector: ""\n')
        fields = resource_spec.get("fields")
        if not isinstance(fields, Mapping):
            add_placeholder(
                ("fields",),
                "fields:  # add field mappings",
                'fields:\n  field_name:\n    selector: ""\n',
            )
        else:
            for field_name, field_spec in fields.items():
                if not isinstance(field_spec, Mapping):
                    continue
                if "selector" not in field_spec:
                    add_placeholder(
                        ("fields", str(field_name), "selector"),
                        f"fields.{field_name}.selector",
                        f'  {field_name}:\n    selector: ""\n',
                    )
                if "transforms" not in field_spec:
                    add_placeholder(
                        ("fields", str(field_name), "transforms"),
                        f"fields.{field_name}.transforms",
                        f"  {field_name}:\n    transforms: []\n",
                    )
        if "extends" not in resource_spec:
            add_placeholder(("extends",), "extends: base_resource", "extends: base_resource\n")
    else:
        # Unknown kind: recommend declaring kind at minimum
        if "kind" not in resource_spec:
            add_placeholder(("kind",), "kind: list|table", "kind: list\n")
    return placeholders


def prepare_insert_snippet(spec: PlaceholderSpec, existing_text: str) -> str:
    """Adjust placeholder snippet before insertion into the editor."""

    snippet = spec.snippet
    if spec.path and spec.path[0] == "fields" and not snippet.lstrip().startswith("fields"):
        if "fields:" not in existing_text:
            snippet = "fields:\n" + snippet
        elif existing_text.rstrip().endswith("fields:"):
            snippet = "  " + snippet.lstrip()
    if not snippet.endswith("\n"):
        snippet += "\n"
    return snippet


__all__ = [
    "FragmentError",
    "PlaceholderSpec",
    "apply_fragment",
    "clean_fragment_text",
    "generate_placeholders",
    "load_rules",
    "parse_fragment_yaml",
    "prepare_insert_snippet",
    "resource_fragment_yaml",
]
