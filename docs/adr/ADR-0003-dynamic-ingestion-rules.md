---
title: "ADR-0003: Dynamic Ingestion Rule Architecture"
status: accepted
date: 2025-09-26
tags: [ingestion, rules, extensibility, sandbox, gui]
---

## Context

Initial ingestion relied on embedded parser functions tightly coupled to specific
HTML structures (ranking tables, team rosters). As coverage expands (club overviews,
historical player stats, derived fields, experimental transforms) a static parser
set becomes brittle:

* Frequent code edits required for minor selector changes.
* Hard to experiment with new extraction fields or temporary analysis columns.
* Difficult to diff rule changes over time or rollback a prior configuration.
* Limited ability for advanced users / plugins to add extraction logic without
  modifying core modules.

We need a declarative rule system enabling users (through the Ingestion Lab GUI)
to:
1. Define resources (logical datasets) with selectors.
2. Map extracted fields to schema columns or sandbox tables.
3. Apply chained safe transforms (whitespace, number parsing, date normalization, etc.).
4. Enforce data quality gates before apply.
5. Version and rollback rule sets.
6. Safely simulate before mutating the canonical database.

## Decision

Adopt a dynamic, versioned JSON rule document parsed into an internal `RuleSet`
model. The ingestion pipeline gains an adapter layer translating `RuleSet`
entries into resource extraction operations instead of calling static parser
functions per HTML type.

Key architectural elements:

| Component                 | Responsibility                                                   |
|---------------------------|------------------------------------------------------------------|
| Rule Document (JSON)      | Declarative source of truth (user editable, versioned)          |
| `RuleSet` Parser          | Validate structure, normalize defaults                          |
| Adapter Layer             | Execute selectors against HTML, yield structured rows           |
| SafeApplyGuard            | Simulation + validation (coverage, quality gates, safety flags) |
| Version Store             | Persist textual & parsed snapshots for rollback                 |
| Draft Autosave            | Non-destructive WIP persistence until explicit publish          |

## Alternatives Considered

1. **Static Parser Classes** (one class per resource type)
   - Pros: Strong typing, explicit code review for changes.
   - Cons: High friction for iteration; proliferation of near-duplicate logic.

2. **Embedded DSL in Python** (define rules as Python structures / lambdas)
   - Pros: Leverages full language expressiveness.
   - Cons: Safety & sandboxing complexity, harder to diff & audit changes.

3. **Hybrid (Static base + overlay JSON)**
   - Pros: Fixed core with user overrides.
   - Cons: Two sources of truth; precedence rules increase complexity early.

Chosen dynamic JSON approach balances flexibility, safety, and versionability.

## Consequences

Positive:
* Rapid iteration: Simple selector or mapping adjustments require no code deploy.
* Reproducibility: Versioned JSON documents capture exact historical extraction definitions.
* Extensibility: Future plugin transforms can register without editing core logic.

Trade-offs:
* Runtime validation overhead vs compile-time guarantees; mitigated by caching parsed `RuleSet` if needed.
* Need robust safety gating (e.g., disallow custom Python) to prevent abuse; addressed via settings flag.
* Must ensure performance of large batch previews (telemetry + perf badge guide tuning).

## Implementation Notes

* Draft file `.ingestion_rules_draft.json` enables non-destructive editing.
* `TelemetryService` offers preview/apply metrics for tuning thresholds.
* `SettingsService` governs batch size caps, performance warning threshold, and safety toggles.
* Events (`GUIEvent.INGEST_RULES_APPLIED` / `GUIEvent.INGEST_RULES_PUBLISHED`) allow other UI components (status bar, freshness indicators) to react.

## Future Enhancements
* Transform pipeline registry with pluggable operation classes.
* Expression sandbox using restricted AST walker (whitelist nodes / functions).
* Cross-file dependency graph influencing incremental re-parse decisions.
* Rule linting (unused selectors, ambiguous mappings) prior to publish.

## Status
Accepted. Initial slice implemented across milestones 7.10.1–7.10.52.

## References
* Roadmap: `roadmaps/implementation_GUI.txt`
* Developer Guide: `docs/source/ingestion_rule_developer_guide.rst`
* Core: `gui/ingestion/rule_schema.py`, `gui/ingestion/rule_apply_guard.py`

---
