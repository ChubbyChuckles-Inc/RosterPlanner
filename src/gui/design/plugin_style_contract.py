"""Plugin UI style contract enforcement (Milestone 0.27).

Ensures plugin-provided style configuration maps only to existing design tokens
and does not introduce ad-hoc hex colors or disallowed properties.

Scope (initial implementation):
- Validate a style mapping dict[str, str] where values must be token references
  of the form ``token:<category>/<name>`` (e.g. ``token:color/background``)
  or approved semantic roles (future extension).
- Detect raw hex strings ("#AABBCC" forms) and flag as violations.
- Provide scanning helper for plugin style definition files.

Not in scope yet:
- Deep property schema validation (will come with component contract work).
- Automatic token suggestion.
"""

from __future__ import annotations

from dataclasses import dataclass
import re
from pathlib import Path
from typing import Dict, Iterable, List, Mapping, Optional, Sequence

__all__ = [
    "PluginStyleIssue",
    "validate_style_mapping",
    "scan_plugin_style_files",
]

TOKEN_REF_RE = re.compile(r"^token:[a-zA-Z0-9_\-]+/[a-zA-Z0-9_\-]+$")
HEX_RE = re.compile(r"#[0-9a-fA-F]{3}(?:[0-9a-fA-F]{3})?(?:[0-9a-fA-F]{2})?")


@dataclass(frozen=True)
class PluginStyleIssue:
    kind: str  # 'invalid-token-ref', 'raw-hex', 'file-parse'
    key: str | None
    value: str | None
    message: str
    file: str | None = None


def validate_style_mapping(mapping: Mapping[str, str]) -> List[PluginStyleIssue]:
    """Validate a plugin style mapping.

    Parameters
    ----------
    mapping: Mapping[str, str]
        Keys are style semantic identifiers; values must be token references.
    """
    issues: List[PluginStyleIssue] = []
    for k, v in mapping.items():
        if HEX_RE.search(v):
            issues.append(
                PluginStyleIssue(
                    kind="raw-hex",
                    key=k,
                    value=v,
                    message="Raw hex color not allowed; use token:<category>/<name> reference.",
                )
            )
            continue
        if not TOKEN_REF_RE.match(v):
            issues.append(
                PluginStyleIssue(
                    kind="invalid-token-ref",
                    key=k,
                    value=v,
                    message="Value must be token:<category>/<name> format.",
                )
            )
    return issues


def _iter_file_lines(path: Path) -> Iterable[str]:
    try:
        with path.open("r", encoding="utf-8", errors="ignore") as f:
            for line in f:
                yield line.rstrip("\n")
    except OSError:
        return


def scan_plugin_style_files(
    paths: Sequence[str],
    prefix: str = "STYLE_",
    max_lines: int = 4000,
) -> List[PluginStyleIssue]:
    """Scan Python files for simple style mapping assignments.

    Heuristic implementation: looks for lines like
        STYLE_BUTTON = {"bg": "token:color/surface"}
    and attempts to eval the RHS in a restricted literal-only context.

    Parameters
    ----------
    paths: Files to scan.
    prefix: Variable prefix signaling style mapping.
    max_lines: Safety cap to avoid huge files.
    """
    collected: List[PluginStyleIssue] = []
    for p in paths:
        path = Path(p)
        lines = []
        for idx, line in enumerate(_iter_file_lines(path)):
            if idx >= max_lines:
                break
            lines.append(line)
        text = "\n".join(lines)
        # Simple pattern: VAR = { ... }
        assign_re = re.compile(
            rf"^({prefix}[A-Z0-9_]+)\s*=\s*(\{{.*?\}})", re.MULTILINE | re.DOTALL
        )
        for m in assign_re.finditer(text):
            var_name = m.group(1)
            dict_text = m.group(2)
            try:
                # Safe-ish literal eval by restricting globals/locals; still rely on Python literal grammar.
                mapping_obj = eval(
                    dict_text, {"__builtins__": {}}, {}
                )  # noqa: S307 - controlled context
                if isinstance(mapping_obj, dict) and all(
                    isinstance(v, str) for v in mapping_obj.values()
                ):
                    issues = validate_style_mapping(mapping_obj)  # noqa: PLW2901
                    for issue in issues:
                        collected.append(issue)
                else:
                    collected.append(
                        PluginStyleIssue(
                            kind="file-parse",
                            key=var_name,
                            value=None,
                            message="Style mapping must be a dict[str, str] of token references.",
                            file=str(path),
                        )
                    )
            except Exception as exc:  # noqa: BLE001
                collected.append(
                    PluginStyleIssue(
                        kind="file-parse",
                        key=var_name,
                        value=None,
                        message=f"Failed to parse style mapping: {exc}",
                        file=str(path),
                    )
                )
    return collected
