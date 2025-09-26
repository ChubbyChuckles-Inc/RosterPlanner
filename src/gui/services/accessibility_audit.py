"""Accessibility audit utilities (Milestone 7.10.68).

Provides lightweight, non-invasive auditing of widget trees to surface
basic a11y issues early in development & CI:
 - Focusability: Interactive widgets (buttons, edits, lists, trees, tables)
   must expose a focus policy other than Qt.FocusPolicy.NoFocus.
 - Object naming: Interactive widgets should have an objectName (for
   test hooks + assistive tech mappings in future adapters).
 - Theme contrast sanity: Validates text.primary vs background.primary
   contrast ratio if ThemeService is available (>= 4.5:1 WCAG AA body text).

The audit intentionally avoids deep platform accessibility API introspection
(which would require OS-specific bridges) and focuses on deterministic checks
we can perform headlessly in tests.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import List, Dict, Any
from PyQt6.QtWidgets import (
    QWidget,
    QPushButton,
    QToolButton,
    QLineEdit,
    QPlainTextEdit,
    QTextEdit,
    QTreeWidget,
    QTreeView,
    QTableWidget,
    QTableView,
)
from PyQt6.QtCore import Qt

try:  # contrast utility (best effort)
    from gui.design.contrast import contrast_ratio  # type: ignore
except Exception:  # pragma: no cover

    def contrast_ratio(a: str, b: str) -> float:  # type: ignore
        return 10.0  # sentinel high value


@dataclass
class AccessibilityReport:
    """Container for audit findings.

    Attributes
    ----------
    missing_focus : list[str]
        Object names (or class names) for interactive widgets lacking focus.
    unnamed_interactive : list[str]
        Class names for interactive widgets without objectName set.
    contrast_issues : list[str]
        Descriptions of theme contrast problems.
    meta : dict[str, Any]
        Additional metadata (counts, etc.).
    """

    missing_focus: List[str] = field(default_factory=list)
    unnamed_interactive: List[str] = field(default_factory=list)
    contrast_issues: List[str] = field(default_factory=list)
    meta: Dict[str, Any] = field(default_factory=dict)

    def ok(self) -> bool:
        return not (self.missing_focus or self.unnamed_interactive or self.contrast_issues)


_INTERACTIVE_TYPES = (
    QPushButton,
    QToolButton,
    QLineEdit,
    QPlainTextEdit,
    QTextEdit,
    QTreeWidget,
    QTreeView,
    QTableWidget,
    QTableView,
)


def _is_interactive(w: QWidget) -> bool:
    return isinstance(w, _INTERACTIVE_TYPES)


def audit_widget_tree(root: QWidget) -> AccessibilityReport:
    """Audit a widget subtree rooted at ``root``.

    Parameters
    ----------
    root : QWidget
        The root widget whose children will be traversed (depth-first).

    Returns
    -------
    AccessibilityReport
        Aggregate report of discovered issues.
    """
    rep = AccessibilityReport()
    stack = [root]
    visited = 0
    interactive_count = 0
    while stack:
        w = stack.pop()
        visited += 1
        if _is_interactive(w):
            interactive_count += 1
            pol = w.focusPolicy()
            if pol == Qt.FocusPolicy.NoFocus:
                rep.missing_focus.append(w.objectName() or w.metaObject().className())
            if not w.objectName():
                rep.unnamed_interactive.append(w.metaObject().className())
        for child in w.findChildren(QWidget, options=Qt.FindChildOption.FindDirectChildrenOnly):
            stack.append(child)
    rep.meta = {"visited": visited, "interactive": interactive_count, "root": root.objectName()}

    # Theme contrast check (optional)
    try:  # best effort; skip if theme service absent
        from gui.services.service_locator import services  # type: ignore

        theme = services.try_get("theme_service")
        if theme is not None:
            colors = theme.colors()  # type: ignore[attr-defined]
            bg = colors.get("background.primary")
            txt = colors.get("text.primary")
            if isinstance(bg, str) and isinstance(txt, str):
                try:
                    cr = contrast_ratio(txt, bg)
                    if cr < 4.5:
                        rep.contrast_issues.append(
                            f"text.primary vs background.primary contrast {cr:.2f} < 4.5"
                        )
                except Exception:  # pragma: no cover
                    pass
    except Exception:  # pragma: no cover
        pass
    return rep


__all__ = ["AccessibilityReport", "audit_widget_tree"]
