# ADR-0013: Migration Preview Diff Generation

Date: 2025-09-25
Status: Accepted
Milestone: 7.10.13

## Context

The ingestion lab needs to show users a non-destructive preview of schema changes implied by the current `RuleSet` + mapping inference compared to the live SQLite database. This enables safe iteration before committing migrations.

## Decision

Implement a pure-logic module `gui.ingestion.rule_migration` that:

1. Introspects existing tables via `SELECT name FROM sqlite_master` and `PRAGMA table_info`.
2. Builds expected schema from `RuleSet` by reusing `build_mapping_entries` + `group_by_resource`.
3. Produces ordered `MigrationAction` records of three kinds:
   - `create_table` with full `CREATE TABLE` SQL when table is missing.
   - `add_column` with `ALTER TABLE ... ADD COLUMN` when a column is missing.
   - `type_note` informational note when a column exists but declared type differs.
4. Returns a `MigrationPreview` for GUI consumption; it does not execute any SQL.
5. Keeps SQLite type mapping minimal: NUMBER -> REAL, DATE/TEXT/UNKNOWN -> TEXT.

## Rationale

- Separation of concerns: keeps diff logic independent from GUI & DB apply paths.
- Deterministic output simplifies unit testing and downstream UI rendering.
- Avoids premature complexity (no destructive ops, no table rebuild for type change).
- Leverages existing mapping inference to ensure a single source of truth.

## Alternatives Considered

- Direct diff inside existing sandbox module: rejected to preserve single responsibility.
- Including destructive ALTER / table rebuild now: deferred to later milestone to minimize risk.

## Consequences

- Additional action kinds (rename, drop) can be appended later without breaking existing UI by feature-detecting new kinds.
- Users with type mismatches must perform manual migration until a future automated path is implemented.

## Testing

Added `tests/test_rule_migration.py` covering:

- New table creation preview.
- Type mismatch note when live column type diverges.

## Future Work

- Integrate with GUI panel (action list + copy SQL button).
- Add detection of orphan columns (potential clean-up advisory) – later milestone.
- Provide structured severity (info/warn) classification.
