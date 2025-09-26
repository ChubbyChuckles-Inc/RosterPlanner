Ingestion Rule Developer Guide
==============================

Milestone: 7.10.52

This guide documents the structure of the dynamic ingestion rule system used by
the Ingestion Lab panel. It is aimed at developers extending the rule schema or
adding new extraction / transform capabilities.

Goals
-----
* Declarative: Rules are JSON (optionally YAML later) documents – easy to diff & version.
* Safe: Potentially dangerous constructs (e.g. custom Python expressions) can be disabled via settings.
* Extensible: New resource types, transforms, and validation passes can be registered without modifying core parsing logic.

Top-Level Rule Document Structure
---------------------------------

::

   {
     "resources": {
       "ranking_table": {"selector": "table.ranking"},
       "team_roster": {"selector": "table.roster"}
     },
     "mapping": {
       "ranking_table.team": "teams.name",
       "ranking_table.points": "teams.points"
     },
     "quality_gates": {
       "ranking_table.points": {"min_ratio": 0.95}
     },
     "transforms": {
       "collapseWhitespace": true,
       "numberParse": {"locale": "de_DE"}
     }
   }

Sections
--------
resources
  Each key represents a logical extracted resource. Minimal form currently requires a ``selector``.
mapping
  Optional block mapping extracted resource.field names to database columns (table.column). Missing mappings are reported by the orphan field detector.
quality_gates
  Per-field thresholds enforcing minimum non-null ratios; evaluated during simulation.
transforms
  Global (pipeline-level) transform hints; future milestones will convert these to a structured transform chain per field.

Versioning & Drafts
-------------------
The rule editor content is autosaved to a draft file (``.ingestion_rules_draft.json``) until explicitly published. Publish creates a versioned entry stored via ``RuleSetVersionStore`` (see milestone 7.10.33). Rollback loads the previous JSON version without applying it.

Simulation & Apply Flow
-----------------------
1. User previews one or more files – no mutation, purely reads.
2. User runs Simulate – ``SafeApplyGuard.simulate`` adapts rules to resources, computes coverage, applies quality gates.
3. If passed, Apply writes an audit entry and (later milestones) updates provenance with rule version id.

Extending the Rule Schema
-------------------------
Add a new transform:
 1. Implement a pure function in ``gui/ingestion/transforms/<name>.py`` with signature ``apply(value: str, config: dict) -> str``.
 2. Register it in a transform registry (future planned module) or import on demand inside the adapter.
 3. Add validation (e.g. allowed keys) in the schema parsing stage (``RuleSet.from_mapping``).

Blocking Custom Python
----------------------
The settings flag ``SettingsService.instance.ingestion_disallow_custom_python`` (exposed via environment variable in future) triggers a guard in ``SafeApplyGuard.simulate`` rejecting rule payload structures containing keys with ``python`` substrings.

Telemetry
---------
The optional ``TelemetryService`` records preview and apply counts plus aggregated timing when enabled via environment variable ``INGESTION_TELEMETRY_ENABLED``.

Events
------
The panel emits (when services registered):
* ``GUIEvent.INGEST_RULES_APPLIED`` – after successful apply with counts.
* ``GUIEvent.INGEST_RULES_PUBLISHED`` – after publish (draft -> version) with hash + version.

Testing Guidance
----------------
* Use the existing service locator override context to inject fakes (e.g. fake sqlite connection).
* Prefer constructing small HTML samples inline for transform validation tests.
* Snapshot tests (milestone 7.10.24) store expected extraction results under ``tests/ingestion_snapshots`` (future expansion).

Future Extension Points
-----------------------
* Field-level transform pipelines (list of operations, each with config).
* Expression sandbox with restricted AST whitelist.
* Plugin-contributed resource adapters resolved via entry points or explicit registry.

Changelog
---------
* 7.10.49: Draft + publish mechanics introduced.
* 7.10.50: Settings-backed ingestion performance & safety flags.
* 7.10.51: Telemetry counters added.
* 7.10.52: Developer guide initial version (this document).

See Also
--------
* ``gui/ingestion/rule_schema.py`` – authoritative parse & validation logic.
* ``gui/ingestion/rule_apply_guard.py`` – simulation + apply coordination.
* Roadmap file ``roadmaps/implementation_GUI.txt`` for milestone context.
