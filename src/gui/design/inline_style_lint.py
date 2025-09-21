"""Inline style lint rule (Milestone 0.24).

Forbids inline styling patterns which bypass the design token system.

Goals
-----
Detect risky / non-compliant styling usage patterns in source files:
 - Direct calls to QWidget.setStyleSheet / object.setStyleSheet with hardcoded CSS.
 - Multi-line style sheet assignments using variable names (heuristic).
 - Raw HTML or template fragments containing style="..." attributes.

Provide structured issue reports with file, line number, snippet, and category.

Allow temporary, explicit opt-outs by adding an inline comment containing
`# inline-style-ok` on the same line (use sparingly).

Design Choices
--------------
 - Regex-based scanning (fast, low complexity) rather than AST since style
   usage is typically textual.
 - Provide simple categories to enable selective future suppression.
 - Pure-Python, GUI-agnostic; can be integrated into pre-commit or CI.

Future Extensions
-----------------
 - Parse QSS content and validate against allowed token variables.
 - Track frequency metrics to drive design debt reporting.
 - Add autofix suggestions (e.g. replace with token reference helper).
"""

from __future__ import annotations

from dataclasses import dataclass
import re
from typing import Iterable, List, Optional, Sequence

__all__ = ["InlineStyleIssue", "scan_for_inline_styles"]

INLINE_OK_MARKER = "inline-style-ok"

# Regex patterns
SET_STYLESHEET_CALL = re.compile(r"\.setStyleSheet\(")
STYLE_ATTR = re.compile(r"style=\"")  # HTML style attribute opening
MULTILINE_QSS_START = re.compile(r"(STYLESHEET|QSS)_? = \"{3}")


@dataclass(frozen=True)
class InlineStyleIssue:
    file: str
    line_no: int
    category: str  # 'setStyleSheet', 'style-attr', 'multiline-qss'
    snippet: str


def _iter_file_lines(path: str) -> Iterable[tuple[int, str]]:
    try:
        with open(path, "r", encoding="utf-8", errors="ignore") as f:
            for idx, line in enumerate(f, 1):
                yield idx, line.rstrip("\n")
    except OSError:
        return


def scan_for_inline_styles(
    paths: Sequence[str],
    exclude_substrings: Optional[Sequence[str]] = None,
) -> List[InlineStyleIssue]:
    """Scan files for inline styling patterns.

    Parameters
    ----------
    paths: sequence[str]
        File paths to scan.
    exclude_substrings: sequence[str] | None
        Substrings in file paths to skip (e.g. tests, generated docs).
    """
    excludes = exclude_substrings or []
    issues: List[InlineStyleIssue] = []

    for path in paths:
        if any(ex in path for ex in excludes):
            continue
        for line_no, line in _iter_file_lines(path):
            lower = line.lower()
            if INLINE_OK_MARKER in lower:
                continue  # explicit allow
            stripped = line.strip()
            if SET_STYLESHEET_CALL.search(stripped):
                issues.append(
                    InlineStyleIssue(
                        file=path,
                        line_no=line_no,
                        category="setStyleSheet",
                        snippet=stripped[:200],
                    )
                )
            if STYLE_ATTR.search(stripped):
                issues.append(
                    InlineStyleIssue(
                        file=path,
                        line_no=line_no,
                        category="style-attr",
                        snippet=stripped[:200],
                    )
                )
            if MULTILINE_QSS_START.search(stripped):
                issues.append(
                    InlineStyleIssue(
                        file=path,
                        line_no=line_no,
                        category="multiline-qss",
                        snippet=stripped[:200],
                    )
                )
    return issues
