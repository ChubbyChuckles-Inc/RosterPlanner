# ADR-0016: Single-File Parse Preview

Date: 2025-09-26
Status: Accepted
Milestone: 7.10.16

## Context
The Ingestion Lab requires a quick, isolated way to apply the current `RuleSet` to one HTML file and display extracted records before moving on to batch previews and diffs. We need a backend facility that is fast, pure logic, and testable without the GUI.

## Decision
Add `rule_parse_preview.generate_parse_preview(rule_set, html, apply_transforms=False)` returning a `ParsePreview` dataclass with:
- `summaries`: per-resource counts & warnings.
- `extracted_records`: raw or transformed records (list & table resources).
- `flattened_tables`: identical structure for now; placeholder for future row normalization.
- `match_spans`: selector → count metadata (DOM span highlighting deferred).

Table extraction skips header rows comprised solely of `<th>` cells. List extraction optionally applies transform chains (when `apply_transforms=True`).

## Rationale
- Keeps GUI free of parsing logic; supports unit tests for correctness & edge handling.
- Allows progressive enhancement (later: DOM node offsets, richer diff metadata) without breaking existing callers.
- Minimizes coupling by only requiring BeautifulSoup and existing rule modules.

## Alternatives Considered
- Immediate integration of positional highlighting using a different parser: deferred to avoid complexity and performance regression.
- Always applying transforms: optional flag provides flexibility for fast iteration vs. full coercion.

## Consequences
- Highlighting is count-based until future enhancement.
- Users might see header rows omitted; this is intentional for cleaner data rows.

## Testing
`tests/test_rule_parse_preview.py` validates row extraction, optional transform application, and match selector metadata.

## Future Work
- Add positional index capture (byte offsets) for UI highlighting overlays.
- Expand flattened view to support nested list normalization and composite key inference.
- Provide partial error capture (per-field transform failure markers) for selective UI highlighting.
