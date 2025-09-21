"""Color token drift detector (Milestone 0.23).

Detects ad-hoc / hardcoded color literals creeping into the codebase instead of
approved design token usage. Helps maintain color consistency and simplifies
theme adjustments.

Approach
--------
 - Load canonical token color values from existing design tokens JSON via
   optional helper (caller supplies mapping of allowed hex values to symbolic names).
 - Regex scan source text for hex color literals (#RGB, #RRGGBB, #RRGGBBAA variants).
 - Report occurrences whose normalized hex value is not in allowed set.
 - Provide structured issues with file, line, literal, and context snippet.

Design Choices
--------------
 - Pure-Python, no dependency on Qt.
 - Focus on hex codes; future extension could parse rgb()/hsl().
 - Caller can exclude test directories or generated assets.
 - Normalization expands short #abc to #aabbcc and uppercases for stable comparison.
 - Lightweight; not a full AST parse—sufficient for drift alerting.

Future Extensions
-----------------
 - Add autofix suggestion mapping nearest token by perceptual distance.
 - Integrate into pre-commit or CI gating.
 - Extend to detect inline style attributes / QSS literals outside override layer.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Dict, Iterable, List, Optional, Sequence, Set

__all__ = [
    "ColorDriftIssue",
    "scan_for_color_drift",
    "normalize_hex",
]


# Order alternatives longest to shortest so alternation does not prematurely
# match a 4-digit fragment of a 6-digit literal (e.g. '#123456' being captured
# as '#1234'). Python's regex engine evaluates alternations left-to-right.
HEX_PATTERN = re.compile(r"#(?:[0-9a-fA-F]{8}|[0-9a-fA-F]{6}|[0-9a-fA-F]{4}|[0-9a-fA-F]{3})")


@dataclass(frozen=True)
class ColorDriftIssue:
    file: str
    line_no: int
    literal: str
    normalized: str
    context: str


def normalize_hex(hex_literal: str) -> str:
    """Normalize a hex color code to #RRGGBB or #RRGGBBAA uppercase.

    Expands #RGB and #RGBA forms.
    """

    h = hex_literal.strip()
    if len(h) in (4, 5):  # #RGB or #RGBA
        core = h[1:]
        expanded = "".join(ch * 2 for ch in core)
        h = "#" + expanded
    return h.upper()


def _iter_file_lines(path: str) -> Iterable[tuple[int, str]]:
    try:
        with open(path, "r", encoding="utf-8", errors="ignore") as f:
            for idx, line in enumerate(f, 1):
                yield idx, line.rstrip("\n")
    except OSError:
        return


def scan_for_color_drift(
    paths: Sequence[str],
    allowed_hex_values: Set[str],
    exclude_substrings: Optional[Sequence[str]] = None,
) -> List[ColorDriftIssue]:
    """Scan given file paths for disallowed hex color literals.

    Parameters
    ----------
    paths: sequence[str]
        Files to scan.
    allowed_hex_values: set[str]
        Normalized (uppercase) allowed hex values (#RRGGBB or #RRGGBBAA).
    exclude_substrings: sequence[str] | None
        File path substrings to ignore (e.g., ["tests/", "generated/"]).
    """

    issues: List[ColorDriftIssue] = []
    excludes = exclude_substrings or []
    for path in paths:
        if any(ex in path for ex in excludes):
            continue
        for line_no, line in _iter_file_lines(path):
            for match in HEX_PATTERN.finditer(line):
                lit = match.group(0)
                norm = normalize_hex(lit)
                # Ignore allowed values
                if norm in allowed_hex_values:
                    continue
                # Filter out comments referencing tokens (heuristic)
                if "token" in line.lower() and norm not in allowed_hex_values:
                    pass  # still count; rationale: even commented ad-hoc value could drift
                # record issue
                snippet = line.strip()
                issues.append(
                    ColorDriftIssue(
                        file=path,
                        line_no=line_no,
                        literal=lit,
                        normalized=norm,
                        context=snippet[:200],
                    )
                )
    return issues
