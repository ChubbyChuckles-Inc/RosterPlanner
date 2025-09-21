"""Design Debt Register (Milestone 0.50).

Tracks outstanding design / UX / visual system issues with severity and
remediation targeting to maintain visibility and guide prioritization.

Features
--------
- Dataclass `DesignDebtItem` capturing id, title, severity, description,
  introduced_in, suggested_fix, status, tags, and optional target_version.
- Severity levels: low, medium, high, critical (validated)
- Status values: open, in_progress, closed (validated)
- Registry functions: register, list, get, filter, close (mark closed),
  summarize (counts by severity + open vs closed split)
- Duplicate id protection and immutable dataclass instances (functional updates)

Design Choices
--------------
- Keep module pure-Python, no Qt dependency for easy testing.
- Use functional update via replacement instead of mutating dataclass in place
  to encourage immutable patterns.
- Provide filtering by tag and/or severity for future dashboard use.

Future Enhancements (Not in scope now)
-------------------------------------
- Aging metrics (days open) & SLA breach detection
- Export to markdown / reports
- Risk score weighting across severities
"""

from __future__ import annotations

from dataclasses import dataclass, replace
from typing import Dict, Iterable, List, Optional, Sequence

__all__ = [
    "DesignDebtItem",
    "register_design_debt",
    "get_design_debt",
    "list_design_debt",
    "filter_design_debt",
    "close_design_debt",
    "summarize_design_debt",
    "clear_design_debt",
]

ALLOWED_SEVERITIES = ("low", "medium", "high", "critical")
ALLOWED_STATUS = ("open", "in_progress", "closed")


@dataclass(frozen=True)
class DesignDebtItem:
    """Represents a single design debt entry.

    Attributes:
        debt_id: Unique identifier (short slug)
        title: Short human label
        severity: One of ALLOWED_SEVERITIES
        description: Longer explanation of the debt / issue
        introduced_in: Version or milestone when observed
        suggested_fix: Optional remediation hint
        status: Workflow state (open, in_progress, closed)
        tags: Optional taxonomy tags (e.g., accessibility, theming)
        target_version: Optional planned resolution version/milestone
    """

    debt_id: str
    title: str
    severity: str
    description: str
    introduced_in: str
    suggested_fix: str = ""
    status: str = "open"
    tags: Sequence[str] = ()
    target_version: Optional[str] = None

    def is_open(self) -> bool:  # pragma: no cover trivial
        return self.status != "closed"


_registry: Dict[str, DesignDebtItem] = {}


def _validate_item(item: DesignDebtItem) -> None:
    if item.severity not in ALLOWED_SEVERITIES:
        raise ValueError(f"Invalid severity '{item.severity}' (allowed: {ALLOWED_SEVERITIES})")
    if item.status not in ALLOWED_STATUS:
        raise ValueError(f"Invalid status '{item.status}' (allowed: {ALLOWED_STATUS})")


def register_design_debt(item: DesignDebtItem, *, override: bool = False) -> None:
    """Register a new design debt item.

    Args:
        item: DesignDebtItem instance
        override: Allow replacing existing item with same id
    Raises:
        ValueError: On duplicate without override or invalid fields.
    """
    _validate_item(item)
    if item.debt_id in _registry and not override:
        raise ValueError(f"Duplicate design debt id '{item.debt_id}'")
    _registry[item.debt_id] = item


def get_design_debt(debt_id: str) -> DesignDebtItem:
    return _registry[debt_id]


def list_design_debt(include_closed: bool = True) -> List[DesignDebtItem]:
    values = list(_registry.values())
    if include_closed:
        return values
    return [v for v in values if v.status != "closed"]


def filter_design_debt(
    *, severities: Iterable[str] | None = None, tags: Iterable[str] | None = None
) -> List[DesignDebtItem]:
    severities_set = set(severities) if severities else None
    tags_set = set(tags) if tags else None
    out: List[DesignDebtItem] = []
    for item in _registry.values():
        if severities_set and item.severity not in severities_set:
            continue
        if tags_set and not (tags_set.intersection(item.tags)):
            continue
        out.append(item)
    return out


def close_design_debt(debt_id: str) -> DesignDebtItem:
    item = get_design_debt(debt_id)
    if item.status == "closed":  # idempotent
        return item
    closed = replace(item, status="closed")
    _registry[debt_id] = closed
    return closed


def summarize_design_debt() -> Dict[str, int]:
    summary: Dict[str, int] = {f"severity_{s}": 0 for s in ALLOWED_SEVERITIES}
    summary.update({"open": 0, "closed": 0})
    for item in _registry.values():
        summary[f"severity_{item.severity}"] += 1
        if item.status == "closed":
            summary["closed"] += 1
        else:
            summary["open"] += 1
    return summary


def clear_design_debt() -> None:
    _registry.clear()
