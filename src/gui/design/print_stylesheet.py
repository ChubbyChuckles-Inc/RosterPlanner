"""Print-friendly stylesheet generator (Milestone 0.28).

Generates a lightweight high-contrast stylesheet suitable for printing / export
contexts (e.g., saving roster or schedule views). The stylesheet intentionally
simplifies visuals: removes animations, neutralizes backgrounds, enforces a
legible font size baseline, and ensures sufficient contrast for grayscale
printers.

Core goals:
- Deterministic output string for easy snapshot testing.
- High contrast variant optional.
- Token-aware: caller provides minimal token dict (subset) to avoid coupling.

Not a full theming engine; this is a focused utility.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, Optional

__all__ = ["PrintStylesheetMeta", "build_print_stylesheet"]


@dataclass(frozen=True)
class PrintStylesheetMeta:
    lines: int
    high_contrast: bool
    included_tokens: int


_BASE_RULES = [
    "* {\n  animation: none !important;\n  transition: none !important;\n}",
    "QWidget {\n  background: #FFFFFF;\n  color: #000000;\n  font-size: 11pt;\n}",
    "QTableView, QTreeView {\n  gridline-color: #000000;\n}",
    "QHeaderView::section {\n  background: #FFFFFF;\n  color: #000000;\n  border: 1px solid #000000;\n}",
]

_HIGH_CONTRAST_OVERRIDES = [
    "QWidget { background: #FFFFFF; color: #000000; }",
    "QPushButton { background: #FFFFFF; border: 2px solid #000000; color: #000000; }",
]

_TOKEN_RULE_TEMPLATE = "/* token:{key} */ :root {{ --{key}: {value}; }}"


def build_print_stylesheet(
    tokens: Optional[Dict[str, str]] = None, high_contrast: bool = True
) -> tuple[str, PrintStylesheetMeta]:
    """Build the print stylesheet string and metadata.

    Parameters
    ----------
    tokens: Optional mapping of token keys to values (string). Only basic color
        and spacing tokens relevant to printing need be provided.
    high_contrast: Whether to include high contrast overrides.

    Returns
    -------
    (stylesheet, meta) tuple where stylesheet is a deterministic string.
    """
    token_rules = []
    if tokens:
        # Deterministic order
        for k in sorted(tokens.keys()):
            token_rules.append(_TOKEN_RULE_TEMPLATE.format(key=k, value=tokens[k]))
    parts = list(_BASE_RULES)
    if high_contrast:
        parts.extend(_HIGH_CONTRAST_OVERRIDES)
    parts.extend(token_rules)
    stylesheet = "\n\n".join(parts) + "\n"
    meta = PrintStylesheetMeta(
        lines=len(stylesheet.strip().splitlines()),
        high_contrast=high_contrast,
        included_tokens=len(token_rules),
    )
    return stylesheet, meta
