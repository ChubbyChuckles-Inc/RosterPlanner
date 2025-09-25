"""Single-File Parse Preview (Milestone 7.10.16)

Provides a pure logic helper to apply a ``RuleSet`` to a single HTML document
and produce structured preview artifacts for the GUI:

Artifacts
---------
* extracted_records: list[dict] per resource (table rows or list item objects)
* resource_summaries: lightweight metadata (counts, missing selectors)
* match_spans: mapping resource -> list of (selector, count)
  (Exact DOM character span highlighting deferred; BeautifulSoup lacks
   native positional tracking without extra parser cost. We expose counts now
   and can later enrich with a different parser if needed.)
* flattened_tables: mapping resource -> list[dict] (for list rules identical
  to extracted_records; for table rules each row is a dict of column->text)

Design Notes
------------
 - Keeps dependency surface minimal: BeautifulSoup only.
 - Does not persist data or mutate any DB.
 - Ignores transforms at this stage for speed; transform application can be
   layered by coercion preview if needed. (We include an option to apply them
   when desired.)
 - Error isolation: malformed selectors fail soft (recorded as warnings) and
   resource extraction continues.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, List, Mapping, Any, Optional
import time
import tracemalloc
from bs4 import BeautifulSoup

from .rule_schema import RuleSet, TableRule, ListRule
from .rule_transforms import apply_transform_chain

__all__ = [
    "ParsePreview",
    "ResourceSummary",
    "generate_parse_preview",
]


@dataclass
class ResourceSummary:
    resource: str
    kind: str
    record_count: int
    warnings: List[str]

    def to_mapping(self) -> Mapping[str, object]:  # pragma: no cover - trivial
        return {
            "resource": self.resource,
            "kind": self.kind,
            "record_count": self.record_count,
            "warnings": list(self.warnings),
        }


@dataclass
class ParsePreview:
    summaries: List[ResourceSummary]
    extracted_records: Dict[str, List[Mapping[str, Any]]]
    flattened_tables: Dict[str, List[Mapping[str, Any]]]
    match_spans: Dict[str, List[Mapping[str, Any]]]
    parse_time_ms: float
    node_count: int
    memory_delta_kb: float
    errors: List[Mapping[str, Any]]  # structured errors for error channel integration

    def to_mapping(self) -> Mapping[str, object]:  # pragma: no cover - trivial
        return {
            "summaries": [s.to_mapping() for s in self.summaries],
            "extracted_records": self.extracted_records,
            "flattened_tables": self.flattened_tables,
            "match_spans": self.match_spans,
        }


def _extract_table(
    rule_name: str, rule: TableRule, soup: BeautifulSoup
) -> tuple[List[dict], List[str], List[Mapping[str, Any]]]:
    warnings: List[str] = []
    rows_out: List[dict] = []
    match_data: List[Mapping[str, Any]] = []
    try:
        table_el = soup.select_one(rule.selector)
    except Exception as e:  # pragma: no cover - selector error path
        return [], [f"Selector error for table '{rule_name}': {e}"], []
    if not table_el:
        return [], [f"Table selector matched 0 nodes ({rule.selector})"], []
    # Naive row extraction: <tr> children; cells as text.
    trs = table_el.find_all("tr")
    for tr in trs:
        cells = tr.find_all(["td", "th"])
        if not cells:
            continue
        # Skip pure header rows (all th elements)
        if all(c.name.lower() == "th" for c in cells):
            continue
        values = {}
        for idx, col in enumerate(rule.columns):
            try:
                cell_text = cells[idx].get_text(strip=True) if idx < len(cells) else ""
            except Exception:
                cell_text = ""
            values[col] = cell_text
        if any(v for v in values.values()):
            rows_out.append(values)
    match_data.append({"selector": rule.selector, "count": len(rows_out)})
    return rows_out, warnings, match_data


def _extract_list(
    rule_name: str, rule: ListRule, soup: BeautifulSoup, allow_expr: bool, apply_transforms: bool
) -> tuple[List[dict], List[str], List[Mapping[str, Any]]]:
    warnings: List[str] = []
    out: List[dict] = []
    match_data: List[Mapping[str, Any]] = []
    try:
        root = soup.select_one(rule.selector)
    except Exception as e:  # pragma: no cover
        return [], [f"Selector error for list '{rule_name}': {e}"], []
    if not root:
        return [], [f"List selector matched 0 nodes ({rule.selector})"], []
    try:
        items = root.select(rule.item_selector)
    except Exception as e:  # pragma: no cover
        return [], [f"Item selector error for list '{rule_name}': {e}"], []
    for el in items:
        record = {}
        for fname, fmap in rule.fields.items():
            val_el = None
            try:
                val_el = el.select_one(fmap.selector)
            except Exception:
                warnings.append(f"Field '{fname}' selector error")
            raw_text = val_el.get_text(strip=True) if val_el else ""
            if apply_transforms and fmap.transforms:
                try:
                    coerced = apply_transform_chain(
                        raw_text, fmap.transforms, allow_expressions=allow_expr
                    )
                except Exception as e:  # pragma: no cover - transform failure path
                    warnings.append(f"Field '{fname}' transform error: {e}")
                    coerced = None
                record[fname] = coerced
            else:
                record[fname] = raw_text
        if any(v for v in record.values()):  # avoid empty records
            out.append(record)
    match_data.append({"selector": rule.selector, "count": len(items)})
    match_data.append({"selector": f"{rule.selector} -> {rule.item_selector}", "count": len(items)})
    return out, warnings, match_data


def generate_parse_preview(
    rule_set: RuleSet,
    html: str,
    *,
    apply_transforms: bool = False,
    capture_performance: bool = True,
) -> ParsePreview:
    """Generate a parse preview for a single HTML document.

    Parameters
    ----------
    rule_set : RuleSet
        Active rule set.
    html : str
        Raw HTML document text.
    apply_transforms : bool, default False
        When True, run transform chains for list rule fields; otherwise return raw text.
    """
    t0 = time.perf_counter()
    if capture_performance:
        tracemalloc.start()
    soup = BeautifulSoup(html, "html.parser")
    node_count = len(list(soup.descendants))  # linear walk cost acceptable for preview scale
    summaries: List[ResourceSummary] = []
    extracted: Dict[str, List[Mapping[str, Any]]] = {}
    flattened: Dict[str, List[Mapping[str, Any]]] = {}
    match_spans: Dict[str, List[Mapping[str, Any]]] = {}

    errors: List[Mapping[str, Any]] = []
    for rname, res in rule_set.resources.items():
        if isinstance(res, TableRule):
            rows, warns, matches = _extract_table(rname, res, soup)
            extracted[rname] = rows
            flattened[rname] = rows
            match_spans[rname] = matches
            summaries.append(
                ResourceSummary(
                    resource=rname, kind="table", record_count=len(rows), warnings=warns
                )
            )
            for w in warns:
                errors.append(
                    {
                        "resource": rname,
                        "kind": "table",
                        "message": w,
                        "severity": "warning" if "error" not in w.lower() else "error",
                    }
                )
        elif isinstance(res, ListRule):
            rows, warns, matches = _extract_list(
                rname, res, soup, rule_set.allow_expressions, apply_transforms
            )
            extracted[rname] = rows
            flattened[rname] = rows  # identical for list rules currently
            match_spans[rname] = matches
            summaries.append(
                ResourceSummary(resource=rname, kind="list", record_count=len(rows), warnings=warns)
            )
            for w in warns:
                errors.append(
                    {
                        "resource": rname,
                        "kind": "list",
                        "message": w,
                        "severity": "warning" if "error" not in w.lower() else "error",
                    }
                )
        else:  # pragma: no cover
            continue
    if capture_performance:
        current, peak = tracemalloc.get_traced_memory()
        tracemalloc.stop()
        mem_delta_kb = peak / 1024.0
    else:
        mem_delta_kb = 0.0
    elapsed_ms = (time.perf_counter() - t0) * 1000.0
    return ParsePreview(
        summaries=summaries,
        extracted_records=extracted,
        flattened_tables=flattened,
        match_spans=match_spans,
        parse_time_ms=elapsed_ms,
        node_count=node_count,
        memory_delta_kb=mem_delta_kb,
        errors=errors,
    )
