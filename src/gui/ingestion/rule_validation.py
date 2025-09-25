"""Rule Validation Engine (Milestone 7.10.9)

Performs static / structural validation of a ``RuleSet`` against one or more
HTML documents (already scraped & stored). The goal is to provide fast feedback
to the Ingestion Lab before executing full transform chains or DB writes.

Scope (initial):
 - Count matches for each resource *root selector*.
 - For list rules, count item matches and per-field coverage (how many items
   produced at least one node for the field selector).
 - Emit warnings for obviously problematic selectors:
     * Resource root selector returns 0 nodes.
     * List rule item selector returns 0 nodes (while root > 0) .
     * Field coverage == 0 (no item produced the field at all).

Not (yet) included (future milestones may extend):
 - Attribute / regex extraction validation.
 - Transform execution & failure simulation.
 - DOM diffing across versions.
 - Performance metrics (handled later under preview / benchmarking tasks).

Design Notes:
 - Pure logic (no PyQt) for unit testability.
 - Uses BeautifulSoup's CSS selectors (``.select``). This is sufficient for
   the current scraping strategy which already relies on BS4.
 - Keeps returned report structure simple JSON‑serializable dataclasses so the
   GUI layer can render without additional translation.
"""

from __future__ import annotations

from dataclasses import dataclass, field, asdict
from typing import Dict, Mapping, List, Any

from bs4 import BeautifulSoup

from .rule_schema import RuleSet, ListRule, TableRule, RuleError

__all__ = [
    "FieldCoverage",
    "ListRuleReport",
    "TableRuleReport",
    "ValidationReport",
    "validate_rules",
]


@dataclass
class FieldCoverage:
    """Coverage stats for a single field within a list rule.

    matched_items: number of items for which selector yielded >= 1 node
    total_items: total item nodes examined
    coverage: matched_items / total_items (0.0 if total_items == 0)
    raw_matches: total number of matched nodes across all items (for context)
    """

    matched_items: int
    total_items: int
    raw_matches: int

    @property
    def coverage(self) -> float:  # pragma: no cover - trivial
        return 0.0 if self.total_items == 0 else self.matched_items / self.total_items

    def to_mapping(self) -> Mapping[str, Any]:  # JSON friendly
        return {
            "matched_items": self.matched_items,
            "total_items": self.total_items,
            "raw_matches": self.raw_matches,
            "coverage": self.coverage,
        }


@dataclass
class ListRuleReport:
    kind: str = "list"
    selector_count: int = 0
    item_count: int = 0
    fields: Dict[str, FieldCoverage] = field(default_factory=dict)

    def to_mapping(self) -> Mapping[str, Any]:
        return {
            "kind": self.kind,
            "selector_count": self.selector_count,
            "item_count": self.item_count,
            "fields": {k: v.to_mapping() for k, v in self.fields.items()},
        }


@dataclass
class TableRuleReport:
    kind: str = "table"
    selector_count: int = 0

    def to_mapping(self) -> Mapping[str, Any]:
        return {"kind": self.kind, "selector_count": self.selector_count}


@dataclass
class ValidationReport:
    resources: Dict[str, Any] = field(default_factory=dict)
    warnings: List[str] = field(default_factory=list)

    def to_mapping(self) -> Mapping[str, Any]:  # pragma: no cover - trivial
        return {
            "resources": {
                name: (rep.to_mapping() if hasattr(rep, "to_mapping") else asdict(rep))
                for name, rep in self.resources.items()
            },
            "warnings": list(self.warnings),
        }


def _validate_list_rule(rule_name: str, rule: ListRule, soups: List[BeautifulSoup], warnings: List[str]) -> ListRuleReport:
    report = ListRuleReport()
    # Count root selector matches across all docs
    root_matches = []
    for soup in soups:
        root_matches.extend(soup.select(rule.selector))
    report.selector_count = len(root_matches)
    if report.selector_count == 0:
        warnings.append(f"Resource '{rule_name}': selector '{rule.selector}' matched 0 nodes")
        return report
    # Items: for each root, select item_selector relative
    items = []
    for root in root_matches:
        items.extend(root.select(rule.item_selector))
    report.item_count = len(items)
    if report.item_count == 0:
        warnings.append(
            f"Resource '{rule_name}': item_selector '{rule.item_selector}' matched 0 nodes (root had {report.selector_count})"
        )
        return report
    # Field coverage
    for fname, fmap in rule.fields.items():
        matched_items = 0
        raw_matches = 0
        for item in items:
            sel_nodes = item.select(fmap.selector)
            if sel_nodes:
                matched_items += 1
                raw_matches += len(sel_nodes)
        cov = FieldCoverage(matched_items=matched_items, total_items=report.item_count, raw_matches=raw_matches)
        report.fields[fname] = cov
        if cov.matched_items == 0:
            warnings.append(
                f"Resource '{rule_name}': field '{fname}' selector '{fmap.selector}' produced 0 matches across {report.item_count} items"
            )
    return report


def _validate_table_rule(rule_name: str, rule: TableRule, soups: List[BeautifulSoup], warnings: List[str]) -> TableRuleReport:
    report = TableRuleReport()
    total = 0
    for soup in soups:
        total += len(soup.select(rule.selector))
    report.selector_count = total
    if total == 0:
        warnings.append(f"Resource '{rule_name}': selector '{rule.selector}' matched 0 nodes")
    return report


def validate_rules(rule_set: RuleSet, html_docs: Mapping[str, str]) -> ValidationReport:
    """Validate selectors in ``rule_set`` against provided HTML docs.

    Parameters
    ----------
    rule_set: RuleSet
        The rules to validate.
    html_docs: Mapping[str, str]
        Mapping of arbitrary file/display name -> raw HTML content.

    Returns
    -------
    ValidationReport
        Aggregated resource reports and warnings list.
    """
    if not html_docs:
        raise RuleError("validate_rules requires at least one HTML document")
    soups = [BeautifulSoup(src, "html.parser") for src in html_docs.values()]
    warnings: List[str] = []
    resources: Dict[str, Any] = {}
    for name, res in rule_set.resources.items():
        if isinstance(res, ListRule):
            resources[name] = _validate_list_rule(name, res, soups, warnings)
        elif isinstance(res, TableRule):
            resources[name] = _validate_table_rule(name, res, soups, warnings)
        else:  # pragma: no cover - defensive
            warnings.append(f"Resource '{name}': unsupported rule type {type(res).__name__}")
    return ValidationReport(resources=resources, warnings=warnings)
