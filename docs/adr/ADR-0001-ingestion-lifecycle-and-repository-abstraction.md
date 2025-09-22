---
title: "ADR-0001: Ingestion Lifecycle & Repository Abstraction"
status: accepted
date: 2025-09-23
tags: [ingestion, architecture, repositories, sqlite, data-layer]
---

## Context

RosterPlanner ingests scraped HTML assets (ranking tables, team roster pages) into a
SQLite database consumed by the PyQt6 GUI. Earlier iterations coupled ingestion
logic directly to ad-hoc SQL writes and filename heuristics. As the product
expands (player history, planning scenarios, plugins) we require:

1. A stable, testable ingestion lifecycle (discover -> hash check -> parse -> transactional upsert -> provenance & validation).
2. A repository abstraction layer separating GUI/query logic from raw SQL specifics to enable future storage changes (e.g., Postgres, API gateway, or caching tier).
3. Deterministic IDs across runs (for diffability, stable references in UI state, and plugin APIs).
4. Incremental re-ingestion skipping unchanged HTML using content hashes (performance + idempotency).
5. Post-ingest consistency validation to surface orphaned or partial data early.

## Decision

We formalize a layered ingestion architecture with these components:

| Layer         | Responsibility                                         | Key Elements                                                        |
| ------------- | ------------------------------------------------------ | ------------------------------------------------------------------- |
| Scrape Assets | Persist raw HTML from league website                   | `services.pipeline.run_full`, output under `data/`                  |
| Audit         | Discover assets & compute sha1                         | `DataAuditService` -> `DivisionAudit`, `AuditFileInfo`              |
| Coordinator   | Orchestrate transactional per-division ingestion       | `IngestionCoordinator` (SAVEPOINT per division)                     |
| Parsers       | Extract domain entities (teams, players, ranking rows) | Embedded parsing funcs (roster & ranking) (future: extract modules) |
| Repositories  | Read-only domain queries for GUI                       | `TeamRepo`, `PlayerRepo`, etc. (SQLite implementations)             |
| Provenance    | Track file hashes & ingest summaries                   | `provenance`, `provenance_summary` tables + normalized view         |
| Validation    | Post-ingest data integrity checks                      | `ConsistencyValidationService`                                      |
| Caching       | Reduce redundant roster loads                          | `RosterCacheService`                                                |

Key policies:

- Deterministic IDs via `id_map` stable mapping (entity_type + source_key) ensures cross-run referential integrity.
- Each division ingested inside a SAVEPOINT for partial failure isolation.
- Hash comparison prior to parsing avoids needless CPU & DB writes (Milestone 5.9.4).
- A standardized summary row (`provenance_summary`) enables freshness reporting and potential telemetry.
- Validation result is registered in the service locator for UI surfacing.

Repository abstraction intentionally remains _read-only_ for phase 1 to keep mutation pathways centralized inside the ingestion coordinator and future planning modules.

## Alternatives Considered

1. Direct SQL in views / viewmodels.
   - Rejected: tightly couples UI to schema, increases refactor cost.
2. Full ORM (SQLAlchemy / Peewee).
   - Rejected (for now): increases dependency surface and migration complexity; current queries are simple and benefit from lean hand-written SQL.
3. Event-sourced ingestion (append-only change events).
   - Deferred: complexity not justified until multi-source merges or audit trails become requirements.

## Consequences

Positive:

- High testability: services are small, dependency-injected via service locator.
- Deterministic & incremental ingest reduces runtime and risk of downstream churn.
- Clear layering supports plugin extension (e.g., alternative parsers) by inserting at discovery or parsing stages.

Trade-offs:

- Additional upfront code (repositories + coordinator) vs. naive SQL, but repays via maintainability.
- Duplicate parsing logic presently co-located in coordinator; future refactor to dedicated parser modules will further modularize.

## Status & Future Work

Implemented Milestones: 5.9.0–5.9.22 establish audit, ingest coordinator, hash skipping, transactional isolation, error channel, caching, performance baseline, consistency validation, and CLI / command palette hooks.

Planned Enhancements:

- Structured JSONL ingest logging (5.9.24).
- Partial ingest surfacing (5.9.26).
- Plugin-parsers injection points (5.9.27).
- Sanitization hardening (5.9.28).
- Telemetry counters (5.9.29).

## References

- Roadmap file: `roadmaps/implementation_GUI.txt`
- Source modules: `gui/services/ingestion_coordinator.py`, `gui/services/data_audit.py`, `gui/services/consistency_validation_service.py`
- Repositories: `gui/repositories/*` (SQLite implementations)

---
