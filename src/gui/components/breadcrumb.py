"""Breadcrumb Component (Milestone 4.6)

Provides a tiny helper to build a breadcrumb path from a team selection in
the navigation tree (Season -> Division -> Team). Implemented without Qt
widget subclassing to keep it testable; the MainWindow will own a QLabel and
set its text via `BreadcrumbBuilder.build_for_team`.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Optional, Iterable

from gui.navigation_tree_model import NavNode

__all__ = ["BreadcrumbBuilder"]


@dataclass
class BreadcrumbBuilder:
    separator: str = " / "

    def build_for_node(self, node: Optional[NavNode]) -> str:
        if node is None:
            return ""
        parts: list[str] = []
        cur = node
        while cur is not None:
            if cur.kind in {"season", "division", "team"}:
                parts.append(cur.label)
            cur = cur.parent  # type: ignore
        if not parts:
            return ""
        return self.separator.join(reversed(parts))

    def build_for_team_entry(self, team_node: Optional[NavNode]) -> str:
        return self.build_for_node(team_node)
