"""Selector Watchlist persistence and drift computation (Milestone 7.10.A11).

Provides storage for pinned selectors and utilities to evaluate drift between a
recorded baseline match count and the current match count. The evaluation logic
reuses the rule validation engine to keep HTML parsing consistent across
features and to maintain testability (pure functions for the core logic).
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, List, Mapping, Optional, Sequence
import json
import os

from gui.ingestion.rule_schema import ListRule, RuleSet, TableRule
from gui.ingestion.rule_validation import (
    FieldCoverage,
    ListRuleReport,
    TableRuleReport,
    ValidationReport,
    validate_rules,
)

__all__ = [
    "SelectorWatchEntry",
    "SelectorWatchResult",
    "SelectorWatchlistStore",
    "compute_watchlist_drift",
]


_VALID_TARGET_TYPES = {"root", "item", "field"}


@dataclass
class SelectorWatchEntry:
    """A selector pinned for drift monitoring."""

    resource: str
    target_type: str
    target_name: Optional[str] = None
    threshold_percent: int = 50
    baseline_count: int = 0
    last_count: Optional[int] = None

    def __post_init__(self) -> None:
        if not isinstance(self.resource, str) or not self.resource.strip():
            raise ValueError("resource must be a non-empty string")
        if self.target_type not in _VALID_TARGET_TYPES:
            raise ValueError(f"Unsupported target_type: {self.target_type}")
        if self.target_type == "field" and not self.target_name:
            raise ValueError("field watchers require target_name")
        if not 1 <= int(self.threshold_percent) <= 100:
            raise ValueError("threshold_percent must be between 1 and 100")
        self.threshold_percent = int(self.threshold_percent)
        self.resource = self.resource.strip()
        if self.target_name:
            self.target_name = self.target_name.strip()
        self.baseline_count = max(0, int(self.baseline_count))
        if self.last_count is not None:
            self.last_count = max(0, int(self.last_count))

    def identifier(self) -> str:
        target = self.target_name or ""
        return f"{self.resource}:{self.target_type}:{target}"

    def target_label(self) -> str:
        if self.target_type == "root":
            return "Root Selector"
        if self.target_type == "item":
            return "Item Selector"
        if self.target_type == "field":
            return f"Field: {self.target_name}"
        return self.target_type

    def to_mapping(self) -> Dict[str, object]:
        return {
            "resource": self.resource,
            "target_type": self.target_type,
            "target_name": self.target_name,
            "threshold_percent": self.threshold_percent,
            "baseline_count": self.baseline_count,
            "last_count": self.last_count,
        }

    @staticmethod
    def from_mapping(payload: Mapping[str, object]) -> "SelectorWatchEntry":
        return SelectorWatchEntry(
            resource=str(payload.get("resource", "")),
            target_type=str(payload.get("target_type", "")),
            target_name=payload.get("target_name") or None,
            threshold_percent=int(payload.get("threshold_percent", 50)),
            baseline_count=int(payload.get("baseline_count", 0)),
            last_count=(
                int(payload["last_count"]) if payload.get("last_count") is not None else None
            ),
        )


@dataclass
class SelectorWatchResult:
    """Outcome of evaluating a watch entry against the current HTML corpus."""

    identifier: str
    resource: str
    target_type: str
    target_name: Optional[str]
    selector: str
    baseline_count: int
    current_count: int
    delta: int
    drop_percent: float
    threshold_percent: int
    alert: bool
    reason: str = ""

    def status_text(self) -> str:
        if self.alert:
            if self.current_count == 0:
                return "⚠ Zero matches"
            return f"⚠ Drop {self.drop_percent:.1f}%"
        if self.delta > 0:
            return f"▲ +{self.delta}"
        if self.delta < 0:
            return f"▼ {self.delta}"
        return "OK"


class SelectorWatchlistStore:
    """Persist selector watch entries in a JSON document."""

    def __init__(self, path: str):
        self.path = path
        self._entries: Dict[str, SelectorWatchEntry] = {}
        self.load()

    # ------------------------------------------------------------------
    def load(self) -> None:
        if not self.path or not os.path.exists(self.path):
            self._entries = {}
            return
        try:
            with open(self.path, "r", encoding="utf-8", errors="ignore") as fh:
                payload = json.load(fh)
        except (json.JSONDecodeError, OSError):
            self._entries = {}
            return
        entries_raw = payload.get("entries") if isinstance(payload, dict) else None
        self._entries = {}
        if isinstance(entries_raw, list):
            for item in entries_raw:
                if not isinstance(item, Mapping):
                    continue
                try:
                    entry = SelectorWatchEntry.from_mapping(item)
                except ValueError:
                    continue
                self._entries[entry.identifier()] = entry

    def save(self) -> None:
        directory = os.path.dirname(self.path)
        if directory and not os.path.exists(directory):
            os.makedirs(directory, exist_ok=True)
        payload = {"entries": [e.to_mapping() for e in self._entries.values()]}
        tmp_path = f"{self.path}.tmp"
        with open(tmp_path, "w", encoding="utf-8") as fh:
            json.dump(payload, fh, ensure_ascii=False, indent=2)
        os.replace(tmp_path, self.path)

    # ------------------------------------------------------------------
    def upsert(self, entry: SelectorWatchEntry) -> None:
        self._entries[entry.identifier()] = entry

    def remove(self, identifier: str) -> None:
        self._entries.pop(identifier, None)

    def get(self, identifier: str) -> Optional[SelectorWatchEntry]:
        return self._entries.get(identifier)

    def entries(self) -> List[SelectorWatchEntry]:
        return sorted(
            self._entries.values(), key=lambda e: (e.resource, e.target_type, e.target_name or "")
        )

    def to_mapping(self) -> Dict[str, List[Dict[str, object]]]:
        return {"entries": [e.to_mapping() for e in self.entries()]}


# ----------------------------------------------------------------------
# Drift computation


def compute_watchlist_drift(
    rule_set: RuleSet,
    entries: Sequence[SelectorWatchEntry],
    html_docs: Mapping[str, str],
) -> Dict[str, SelectorWatchResult]:
    """Compute drift for ``entries`` using current HTML documents."""

    if not entries:
        return {}
    report = validate_rules(rule_set, html_docs)
    results: Dict[str, SelectorWatchResult] = {}
    for entry in entries:
        selector = _resolve_selector(rule_set, entry)
        current, reason = _extract_current_count(report, entry)
        baseline = entry.baseline_count
        delta = current - baseline
        drop_percent = 0.0
        if baseline > 0 and current < baseline:
            drop_percent = ((baseline - current) / baseline) * 100.0
        drop_percent = round(drop_percent, 2)
        alert = current == 0 or (baseline > 0 and drop_percent >= entry.threshold_percent)
        results[entry.identifier()] = SelectorWatchResult(
            identifier=entry.identifier(),
            resource=entry.resource,
            target_type=entry.target_type,
            target_name=entry.target_name,
            selector=selector,
            baseline_count=baseline,
            current_count=current,
            delta=delta,
            drop_percent=drop_percent,
            threshold_percent=entry.threshold_percent,
            alert=alert,
            reason=reason if alert and reason else "",
        )
    return results


def _resolve_selector(rule_set: RuleSet, entry: SelectorWatchEntry) -> str:
    resource = rule_set.resources.get(entry.resource)
    if resource is None:
        return "<resource missing>"
    if isinstance(resource, TableRule):
        return resource.selector
    if isinstance(resource, ListRule):
        if entry.target_type == "root":
            return resource.selector
        if entry.target_type == "item":
            return resource.item_selector
        if entry.target_type == "field" and entry.target_name:
            field = resource.fields.get(entry.target_name)
            if field:
                return field.selector
        return "<field missing>"
    return "<unsupported resource>"


def _extract_current_count(
    report: ValidationReport,
    entry: SelectorWatchEntry,
) -> tuple[int, str]:
    """Resolve the current match count for ``entry`` from ``report``."""

    rep = report.resources.get(entry.resource)
    if rep is None:
        return 0, "resource missing from validation"
    if isinstance(rep, TableRuleReport):
        if entry.target_type != "root":
            return 0, "table resources expose only the root selector"
        return rep.selector_count, ""
    if isinstance(rep, ListRuleReport):
        if entry.target_type == "root":
            return rep.selector_count, ""
        if entry.target_type == "item":
            return rep.item_count, ""
        if entry.target_type == "field" and entry.target_name:
            field_cov: Optional[FieldCoverage] = rep.fields.get(entry.target_name)
            if not field_cov:
                return 0, "field missing from rule"
            return field_cov.matched_items, ""
        return 0, "unsupported field watch target"
    return 0, "unsupported resource type"
