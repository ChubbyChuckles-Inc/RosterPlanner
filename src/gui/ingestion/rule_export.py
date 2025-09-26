"""Rule set export / import utilities (Milestone 7.10.42).

Provides pure helper functions for writing validated rule documents to disk
and loading them back. Keeps a tight surface area for testability and avoids
extra dependencies (JSON only for now; YAML could be added later if needed).

Design goals:
 - Validate structure via RuleSet.from_mapping before persisting.
 - Normalize on export: ensure version present; pretty JSON indent=2.
 - Reject suspiciously large documents (>2MB) to avoid accidental misuse.
 - Raise ValueError with clear messages for all error modes.

Functions
---------
export_rules(rule_text: str, path: str) -> str
    Validate and write normalized JSON rule set to the given path ('.json' enforced).
import_rules(path: str) -> str
    Load + validate a rule file returning normalized pretty JSON string.
"""

from __future__ import annotations

from typing import Mapping, Any
import json
import os
from .rule_schema import RuleSet, RuleError, RULESET_VERSION

MAX_RULE_DOC_BYTES = 2 * 1024 * 1024  # 2MB safety ceiling

__all__ = ["export_rules", "import_rules"]


def _parse_raw_rules(text: str) -> Mapping[str, Any]:
    if not text or not text.strip():
        raise ValueError("Rule text is empty")
    if len(text) > MAX_RULE_DOC_BYTES:
        raise ValueError("Rule text exceeds size limit (2MB)")
    try:
        data = json.loads(text)
    except Exception as e:  # pragma: no cover - invalid JSON path covered via raise
        raise ValueError(f"Cannot parse rules JSON: {e}") from e
    if not isinstance(data, dict):
        raise ValueError("Root of rule document must be an object/mapping")
    return data


def _normalise_rules_mapping(data: Mapping[str, Any]) -> Mapping[str, Any]:
    # Guarantee version key so round-trip includes schema version.
    if "version" not in data:
        data = dict(data)  # shallow copy
        data["version"] = RULESET_VERSION
    return data


def export_rules(rule_text: str, path: str) -> str:
    """Validate and write rule set to disk, returning the final path.

    The output is always UTF-8 encoded pretty JSON with trailing newline.
    If *path* has no extension, '.json' is appended. Existing files are
    overwritten.
    """

    data = _parse_raw_rules(rule_text)
    data = _normalise_rules_mapping(data)
    # Validate via schema (ensures internal invariants).
    try:
        rs = RuleSet.from_mapping(data)
    except RuleError as e:
        raise ValueError(f"Rule validation failed: {e}") from e
    mapping = rs.to_mapping()
    if not path.lower().endswith(".json"):
        path = path + ".json"
    try:
        with open(path, "w", encoding="utf-8") as fh:
            json.dump(mapping, fh, indent=2, ensure_ascii=False)
            fh.write("\n")
    except Exception as e:  # pragma: no cover - IO errors system dependent
        raise ValueError(f"Failed writing rules to {path}: {e}") from e
    return path


def import_rules(path: str) -> str:
    """Load a rule set file, validate it, and return normalised JSON string."""

    if not os.path.isfile(path):
        raise ValueError(f"Rule file does not exist: {path}")
    try:
        size = os.path.getsize(path)
        if size > MAX_RULE_DOC_BYTES:
            raise ValueError("Rule file exceeds size limit (2MB)")
        with open(path, "r", encoding="utf-8") as fh:
            raw = fh.read()
    except ValueError:
        raise
    except Exception as e:  # pragma: no cover
        raise ValueError(f"Failed reading rule file: {e}") from e
    data = _parse_raw_rules(raw)
    try:
        rs = RuleSet.from_mapping(_normalise_rules_mapping(data))
    except RuleError as e:
        raise ValueError(f"Rule validation failed: {e}") from e
    mapping = rs.to_mapping()
    return json.dumps(mapping, indent=2, ensure_ascii=False) + "\n"
