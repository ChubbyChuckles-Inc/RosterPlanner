"""Rule overlap / conflict detector (Milestone 7.10.A6).

Provides a lightweight heuristic to identify potentially conflicting or
redundant extraction resources whose selectors target overlapping DOM
regions. This assists authors in refining rule specificity and avoiding
duplicate downstream rows.

Design Goals:
- Pure function core (`detect_overlaps`) for easy unit testing.
- Zero external deps beyond BeautifulSoup4 (already in requirements).
- Conservative: only flags direct node overlaps (Jaccard > 0). Future
  enhancements could add percentage thresholds or structural similarity.

Definitions:
For a TableRule we consider the set of table root nodes matching its
`selector`. For a ListRule we consider the set of *item* nodes obtained
by first matching its `selector` (container) then selecting
`item_selector` relative to each container.

Returned overlaps enumerate unordered pairs (A,B) (A< B lexicographically)
with counts and Jaccard index (|A∩B| / |A∪B|).
"""
from __future__ import annotations
from dataclasses import dataclass
from typing import List
from bs4 import BeautifulSoup
from .rule_schema import RuleSet, TableRule, ListRule  # type: ignore

__all__ = ["OverlapRecord", "detect_overlaps"]


@dataclass
class OverlapRecord:
    """Represents overlap statistics between two rule resources."""

    resource_a: str
    resource_b: str
    count_a: int
    count_b: int
    overlap: int
    jaccard: float

    def to_mapping(self) -> dict:  # pragma: no cover - trivial
        return {
            "resource_a": self.resource_a,
            "resource_b": self.resource_b,
            "count_a": self.count_a,
            "count_b": self.count_b,
            "overlap": self.overlap,
            "jaccard": self.jaccard,
        }


def _collect_nodes(rs: RuleSet, html: str) -> dict[str, set[int]]:
    soup = BeautifulSoup(html, "html.parser")
    result: dict[str, set[int]] = {}
    for name, res in rs.resources.items():
        try:
            if isinstance(res, TableRule):
                nodes = soup.select(res.selector) if res.selector else []  # type: ignore[arg-type]
                result[name] = {id(n) for n in nodes}
            elif isinstance(res, ListRule):
                containers = soup.select(res.selector) if res.selector else []  # type: ignore[arg-type]
                item_ids: set[int] = set()
                for c in containers:
                    try:
                        for it in c.select(res.item_selector):  # type: ignore[arg-type]
                            item_ids.add(id(it))
                    except Exception:
                        continue
                result[name] = item_ids
        except Exception:
            # Ignore malformed selectors to keep detector resilient
            continue
    return result


def detect_overlaps(rs: RuleSet, html: str, *, min_jaccard: float = 0.0) -> List[OverlapRecord]:
    """Detect overlapping target node sets among rule resources.

    Parameters
    ----------
    rs: RuleSet
        Parsed rule set containing resources.
    html: str
        HTML document to evaluate selectors against.
    min_jaccard: float, default 0.0
        Minimum Jaccard index required to include a pair in the output.

    Returns
    -------
    list[OverlapRecord]
        Records sorted by descending overlap size then descending jaccard.
    """
    node_map = _collect_nodes(rs, html)
    names = sorted(node_map.keys())
    overlaps: List[OverlapRecord] = []
    for i in range(len(names)):
        a = names[i]
        set_a = node_map[a]
        if not set_a:
            continue
        for j in range(i + 1, len(names)):
            b = names[j]
            set_b = node_map[b]
            if not set_b:
                continue
            inter = set_a & set_b
            if not inter:
                continue
            union = set_a | set_b
            jacc = len(inter) / len(union) if union else 0.0
            if jacc >= min_jaccard:
                overlaps.append(
                    OverlapRecord(
                        resource_a=a,
                        resource_b=b,
                        count_a=len(set_a),
                        count_b=len(set_b),
                        overlap=len(inter),
                        jaccard=round(jacc, 6),
                    )
                )
    overlaps.sort(key=lambda r: (-r.overlap, -r.jaccard, r.resource_a, r.resource_b))
    return overlaps
