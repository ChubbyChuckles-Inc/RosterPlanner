"""Adaptive reflow rules (Milestone 0.21.1).

Defines declarative UI adaptation actions keyed off responsive breakpoints and
intermediate width thresholds (<900px collapse behavior). This preps the view
layer for future dynamic layout adjustments without embedding magic numbers
throughout widget code.

Actions are symbolic; actual implementation (e.g., hiding a dock, switching a
toolbar to icon-only) will be performed in later GUI integration milestones.

Rule Model
----------
Each rule specifies a `predicate` (min <= width < max) and a list of
`actions` describing adaptation directives. Rules are evaluated in order; all
matching rules contribute actions (allowing layering). Actions are unique-ified
while preserving first occurrence order.

Examples of actions (semantic, not imperative):
 - collapse_nav_to_icons
 - hide_secondary_sidebar
 - stack_side_panels
 - reduce_horizontal_padding
 - hide_status_bar_text
 - show_compact_toolbar
 - enable_extra_summary_panel (wide)

Design Considerations
---------------------
 - Avoid direct dependency on responsive.Breakpoint to keep module simple.
 - Provide helper `get_reflow_actions(width)` returning ordered list of actions.
 - Pure data & functions; unit testable without Qt.
 - Thresholds align with breakpoints: 0, 640, 900, 1280, 1600.

Future Extensions
-----------------
 - Add priority or conflict resolution metadata if needed.
 - Introduce action categories (layout, density, visibility) for filtering.
 - Map actions to analytics events for usage tracking.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Callable, List, Tuple

__all__ = [
    "ReflowRule",
    "list_reflow_rules",
    "get_reflow_actions",
]


@dataclass(frozen=True)
class ReflowRule:
    """Declarative adaptation rule.

    Attributes
    ----------
    name: str
        Identifier for debugging / introspection.
    min_width: int
        Inclusive lower bound.
    max_width: int
        Exclusive upper bound (-1 denotes open-ended).
    actions: list[str]
        Semantic action identifiers applied when rule matches.
    """

    name: str
    min_width: int
    max_width: int
    actions: List[str]

    def matches(self, width: int) -> bool:
        upper = None if self.max_width == -1 else self.max_width
        if upper is None:
            return width >= self.min_width
        return self.min_width <= width < upper


_RULES: List[ReflowRule] = []


def _register(rule: ReflowRule) -> None:
    _RULES.append(rule)


# Narrow / XS (<640)
_register(
    ReflowRule(
        name="xs-collapse",
        min_width=0,
        max_width=640,
        actions=[
            "collapse_nav_to_icons",
            "hide_secondary_sidebar",
            "stack_side_panels",
            "reduce_horizontal_padding",
            "show_compact_toolbar",
            "hide_status_bar_text",
        ],
    )
)

# Small / Narrow (>=640 <900): still constrained but more horizontal space
_register(
    ReflowRule(
        name="sm-narrow",
        min_width=640,
        max_width=900,
        actions=[
            "collapse_nav_to_icons",
            "hide_secondary_sidebar",
            "reduce_horizontal_padding",
            "show_compact_toolbar",
        ],
    )
)

# Medium baseline (>=900 <1280): standard layout
_register(
    ReflowRule(
        name="md-standard",
        min_width=900,
        max_width=1280,
        actions=[
            "standard_layout",
        ],
    )
)

# Large (>=1280 <1600): can enable auxiliary panel
_register(
    ReflowRule(
        name="lg-aux",
        min_width=1280,
        max_width=1600,
        actions=[
            "enable_aux_panel",
            "standard_layout",
        ],
    )
)

# Extra large (>=1600): wide enhancements
_register(
    ReflowRule(
        name="xl-wide",
        min_width=1600,
        max_width=-1,
        actions=[
            "enable_aux_panel",
            "enable_extra_summary_panel",
            "standard_layout",
        ],
    )
)


def list_reflow_rules() -> List[ReflowRule]:
    return list(_RULES)


def get_reflow_actions(width: int) -> List[str]:
    if width < 0:
        raise ValueError("Width must be non-negative")
    seen = set()
    ordered: List[str] = []
    for rule in _RULES:
        if rule.matches(width):
            for act in rule.actions:
                if act not in seen:
                    seen.add(act)
                    ordered.append(act)
    return ordered
