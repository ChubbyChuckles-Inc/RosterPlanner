# ADR-0015: Data Type Coercion Preview

Date: 2025-09-26
Status: Accepted
Milestone: 7.10.15

## Context
Users need rapid feedback on whether transform chains will successfully coerce raw extracted string values into intended logical types (numbers, dates, trimmed strings). Providing a preview with success/failure counts and sample outputs reduces iteration time before committing migrations or ingesting large batches.

## Decision
Implemented `rule_coercion.generate_coercion_preview` which:
- Iterates over all resources in the active `RuleSet`.
- Applies transform chains for list rule fields using existing safe execution engine.
- Passes table columns through unchanged (no column-level transforms yet).
- Collects per-field statistics: total, success, failures, distinct error messages (capped at 5), and up to 8 coerced sample values.
- Returns a serializable result structure for GUI visualization (bar charts, badges, etc.).

## Rationale
- Reuses existing transform code; avoids duplication.
- Keeps module pure logic, enabling fast tests and future CLI/automation reuse.
- Conservative limits prevent UI overload while retaining diagnostic value.

## Alternatives Considered
- Streaming callback interface for incremental UI updates: postponed until performance profiling indicates need.
- Storing every failing raw value: rejected to avoid memory blow-up with large samples.

## Consequences
- Table columns show only passthrough behavior until column transforms are introduced (future enhancement).
- Users must correlate failures to raw inputs elsewhere; future improvements could include first failing raw sample reference.

## Testing
Added `tests/test_rule_coercion.py` covering successful coercions, numeric/date failures, and empty sample behavior.

## Future Work
- Include original raw snippet alongside failure messages.
- Add timing metrics for performance hotspot identification.
- Support column-level transforms for table resources.
- Provide a diff view of raw vs coerced string representations.
