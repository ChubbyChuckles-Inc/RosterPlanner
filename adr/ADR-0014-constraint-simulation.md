# ADR-0014: Constraint Simulation Engine

Date: 2025-09-26
Status: Accepted
Milestone: 7.10.14

## Context
Before applying schema migrations it's valuable to surface likely uniqueness and foreign key problems using preview data derived from extraction rules. We need a deterministic, testable mechanism independent of the live database to highlight these issues inside the Ingestion Lab.

## Decision
Introduce `rule_constraints.py` providing `simulate_constraints(rule_set, samples)` that inspects table resources and sample rows to emit structured `ConstraintIssue` objects for:
- `unique_violation`: Duplicate non-null values for heuristic key columns.
- `fk_orphan`: Referencing values not present in parent table id sets.

Heuristics:
- Candidate unique columns: any column named `id` or ending with `_id` in table resources.
- FK inference: columns ending `_id` referencing table with the stem name (singular/plural tolerant) if it exists and has rows.

## Rationale
- Keeps logic pure-Python enabling straightforward unit tests and future reuse in CLI tooling.
- Provides immediate user value while deferring complex constraint modeling (composite keys, explicit declarations) to later milestones.
- Aligns with incremental roadmap approach (minimal risk, fast feedback).

## Alternatives Considered
- Introspecting live DB constraints: current schema lacks explicit constraints—would produce limited signal.
- Requiring explicit constraint declarations now: increases authoring burden prematurely.

## Consequences
- May produce false positives/negatives for unconventional naming—acceptable trade-off for early feedback; users can later supply overrides.
- Future enrichment (severity levels, ignore lists) can extend the result schema without breaking existing consumers.

## Testing
Added `tests/test_rule_constraints.py` covering duplicate id detection and orphan foreign key detection as well as a clean case.

## Future Work
- Allow explicit constraint metadata in rule set or a separate mapping file.
- Composite key detection based on uniqueness patterns in sample rows.
- Severity tagging & grouping for UI presentation.
- Integration test in Ingestion Lab panel once preview data wiring exists.
