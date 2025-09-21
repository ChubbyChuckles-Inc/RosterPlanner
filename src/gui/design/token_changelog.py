"""Design token changelog generation (Milestone 0.42).

This module produces a structured diff (changelog) between two snapshots of
design token JSON files. The goal is to enable auditing of visual changes,
supporting downstream tooling (e.g., automated release notes or style review).

Scope (intentionally minimal / dependency‑light):
 - Pure dict comparison (no semantic color contrast revalidation here).
 - Supports arbitrarily nested mappings of JSON-serialisable primitives.
 - Emits stable, sorted output for deterministic tests.

Public API:
 - ``load_tokens_snapshot(path)``: load raw JSON mapping.
 - ``flatten_tokens(data)``: flatten nested mapping into dot-separated keys.
 - ``diff_tokens(old, new)``: compute added / removed / changed keys.
 - ``generate_changelog(old_path, new_path)``: convenience end-to-end helper.

Design Notes:
 - We flatten rather than performing recursive diff objects for simplicity and
   ease of consumption in tooling (e.g., rendering a table in docs).
 - Changed detection: value inequality (``!=``) – for simple primitives this is
   sufficient; future enhancement could add numeric tolerance for floats.
 - Metadata summarisation groups keys by their first segment (e.g., 'color',
   'spacing', 'typography') to give a quick overview.
 - The module avoids importing the richer ``DesignTokens`` structure to keep it
   usable early in build pipelines (e.g., prior to full package availability).

Edge Cases:
 - Non-mapping top-level JSON -> raises ``TypeError``.
 - Duplicate keys after flattening (should not occur in valid JSON objects) ->
   later assignment wins (standard Python dict semantics); we do not special‑case.
 - Lists: included by index (e.g., ``palette.0``). This keeps implementation
   generic without needing schema knowledge.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, Iterable, Mapping, MutableMapping, Tuple
import json

__all__ = [
    "TokenChange",
    "TokenChangelog",
    "load_tokens_snapshot",
    "flatten_tokens",
    "diff_tokens",
    "generate_changelog",
]


@dataclass(frozen=True)
class TokenChange:
    """Represents a single token key change.

    kind: 'added' | 'removed' | 'changed'
    key: flattened token path (dot notation)
    old: previous value (``None`` if added)
    new: new value (``None`` if removed)
    """

    kind: str
    key: str
    old: Any
    new: Any


@dataclass(frozen=True)
class TokenChangelog:
    """Structured set of token changes with convenience accessors."""

    added: Tuple[TokenChange, ...]
    removed: Tuple[TokenChange, ...]
    changed: Tuple[TokenChange, ...]

    def is_empty(self) -> bool:  # pragma: no cover - trivial
        return not (self.added or self.removed or self.changed)

    def summary_by_category(self) -> Dict[str, Dict[str, int]]:
        """Return counts grouped by first key segment (e.g., 'color')."""
        buckets: Dict[str, Dict[str, int]] = {}
        for coll_name, coll in (
            ("added", self.added),
            ("removed", self.removed),
            ("changed", self.changed),
        ):
            for ch in coll:
                category = ch.key.split(".", 1)[0]
                cat_bucket = buckets.setdefault(category, {"added": 0, "removed": 0, "changed": 0})
                cat_bucket[coll_name] += 1
        return buckets


def load_tokens_snapshot(path: str | Path) -> Mapping[str, Any]:
    """Load a raw token JSON snapshot.

    Raises FileNotFoundError if missing; TypeError if not a mapping root.
    """
    p = Path(path)
    with p.open("r", encoding="utf-8") as f:
        data = json.load(f)
    if not isinstance(data, Mapping):  # Basic guard; detailed schema elsewhere
        raise TypeError("Token snapshot root must be a JSON object (mapping).")
    return data


def flatten_tokens(data: Mapping[str, Any], prefix: str = "") -> Dict[str, Any]:
    """Flatten nested mapping/list structure into dot-notation keys.

    Examples:
        {"color": {"background": {"base": "#fff"}}} ->
            {"color.background.base": "#fff"}
        {"palette": ["#000", "#111"]} ->
            {"palette.0": "#000", "palette.1": "#111"}
    """

    flat: Dict[str, Any] = {}

    def _walk(node: Any, path: str) -> None:
        if isinstance(node, Mapping):
            for k, v in node.items():
                _walk(v, f"{path}.{k}" if path else k)
        elif isinstance(node, list):
            for idx, v in enumerate(node):
                _walk(v, f"{path}.{idx}" if path else str(idx))
        else:
            flat[path] = node

    _walk(data, prefix)
    return flat


def diff_tokens(old: Mapping[str, Any], new: Mapping[str, Any]) -> TokenChangelog:
    """Compute a token changelog between two raw token mappings.

    Returns deterministic ordering (sorted by key within each category).
    """
    old_flat = flatten_tokens(old)
    new_flat = flatten_tokens(new)

    added: list[TokenChange] = []
    removed: list[TokenChange] = []
    changed: list[TokenChange] = []

    old_keys = set(old_flat.keys())
    new_keys = set(new_flat.keys())

    for k in sorted(new_keys - old_keys):
        added.append(TokenChange(kind="added", key=k, old=None, new=new_flat[k]))
    for k in sorted(old_keys - new_keys):
        removed.append(TokenChange(kind="removed", key=k, old=old_flat[k], new=None))
    for k in sorted(old_keys & new_keys):
        if old_flat[k] != new_flat[k]:
            changed.append(TokenChange(kind="changed", key=k, old=old_flat[k], new=new_flat[k]))

    return TokenChangelog(
        added=tuple(added),
        removed=tuple(removed),
        changed=tuple(changed),
    )


def generate_changelog(old_path: str | Path, new_path: str | Path) -> TokenChangelog:
    """High-level convenience API to diff two JSON paths."""
    old = load_tokens_snapshot(old_path)
    new = load_tokens_snapshot(new_path)
    return diff_tokens(old, new)
