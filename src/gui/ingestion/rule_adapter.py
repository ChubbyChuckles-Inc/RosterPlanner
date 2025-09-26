"""Rule Adapter Layer (Milestone 7.10.29).

Converts a generic `RuleSet` (declarative extraction schema) into concrete
parsed row structures suitable for downstream ingestion via the existing
pipeline/ingestion coordinator.

Scope (initial):
- Provide pure functions to apply a RuleSet to a collection of HTML blobs.
- Produce a `AdaptedResource` structure describing extracted rows + kind.
- Focus on a minimal stable interface so the IngestionCoordinator can later
  accept either (a) legacy parser outputs or (b) adapted rule outputs via a
  strategy pattern.

Out of scope for this milestone:
- Direct DB writes (performed later when safe execution guards are in place).
- Mapping to actual schema / coercion (handled by earlier mapping modules).
- Advanced transform / expression security hardening (already gated in RuleSet).

Design:
- `adapt_ruleset_over_files` orchestrates calling `generate_parse_preview` per file
  and aggregating rows by resource name.
- Deduplicates identical rows across files (basic tuple-based de-dupe) to reduce
  downstream churn; retains a source_files list for traceability.
- Returns `AdaptedBundle` with resource->AdaptedResource mapping.

The adapter intentionally builds on the preview engine to avoid duplicating
extraction logic. This keeps maintenance cost low and ensures consistency
between what a user previews and what ultimately gets ingested when applying
rules.
"""

from __future__ import annotations
from dataclasses import dataclass, field
from typing import Dict, List, Mapping, Any, Iterable
from .rule_schema import RuleSet
from .rule_parse_preview import generate_parse_preview

__all__ = ["AdaptedResource", "AdaptedBundle", "adapt_ruleset_over_files"]


@dataclass
class AdaptedResource:
    """Represents aggregated extraction rows for a single resource.

    Attributes
    ----------
    name: str
        Resource name as declared in the RuleSet.
    kind: str
        Either "table" or "list".
    rows: List[Mapping[str, Any]]
        Distinct extracted rows across all processed files.
    source_files: List[str]
        Files that contributed at least one row for this resource.
    warnings: List[str]
        Aggregated warnings encountered during extraction.
    """

    name: str
    kind: str
    rows: List[Mapping[str, Any]] = field(default_factory=list)
    source_files: List[str] = field(default_factory=list)
    warnings: List[str] = field(default_factory=list)

    def to_mapping(self) -> Mapping[str, Any]:  # pragma: no cover - trivial
        return {
            "name": self.name,
            "kind": self.kind,
            "rows": list(self.rows),
            "source_files": list(self.source_files),
            "warnings": list(self.warnings),
        }


@dataclass
class AdaptedBundle:
    resources: Dict[str, AdaptedResource]

    def to_mapping(self) -> Mapping[str, Any]:  # pragma: no cover - trivial
        return {k: v.to_mapping() for k, v in self.resources.items()}


def adapt_ruleset_over_files(rule_set: RuleSet, html_by_file: Mapping[str, str]) -> AdaptedBundle:
    """Apply `rule_set` to each HTML document and aggregate by resource.

    Parameters
    ----------
    rule_set: RuleSet
        Active rule definition set.
    html_by_file: Mapping[str, str]
        Mapping absolute (or logical) filepath -> raw HTML text.

    Returns
    -------
    AdaptedBundle
        Aggregated resource-level extraction artifacts.
    """
    aggregated: Dict[str, AdaptedResource] = {}
    # Temporary per-resource de-dupe set (tuple of sorted items) to avoid duplicate row noise
    dedupe: Dict[str, set] = {r: set() for r in rule_set.resources}
    for fpath, html in html_by_file.items():
        preview = generate_parse_preview(
            rule_set, html, apply_transforms=True, capture_performance=False
        )
        # Build map of warnings per resource from preview summaries
        warn_map = {s.resource: list(s.warnings) for s in preview.summaries}
        for rname, rows in preview.extracted_records.items():
            # Determine kind from summaries (fallback to 'list')
            kind = next((s.kind for s in preview.summaries if s.resource == rname), "list")
            res = aggregated.get(rname)
            if res is None:
                res = AdaptedResource(name=rname, kind=kind)
                aggregated[rname] = res
            if fpath not in res.source_files:
                res.source_files.append(fpath)
            # Append distinct rows
            for row in rows:
                # Normalize row to tuple for de-dupe (order deterministic by sorted keys)
                key = tuple((k, row.get(k)) for k in sorted(row.keys()))
                if key in dedupe[rname]:
                    continue
                dedupe[rname].add(key)
                res.rows.append(dict(row))
            # Merge warnings
            if warn_map.get(rname):
                res.warnings.extend(warn_map[rname])
    return AdaptedBundle(resources=aggregated)
