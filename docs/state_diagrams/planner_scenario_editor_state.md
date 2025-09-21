# Planner Scenario Editor State Diagram

Represents lifecycle while creating or modifying a match planning scenario (lineup configuration + constraints).

## States Overview

```mermaid
digraph PlannerScenarioEditor {
  rankdir=LR;
  Draft -> Validating [label="user edits / save attempt"];
  Validating -> Draft [label="validation errors"];
  Validating -> Ready [label="valid"];
  Ready -> Simulating [label="run optimization"];
  Simulating -> Ready [label="success"];
  Simulating -> Draft [label="canceled / constraints changed"];
  Ready -> Committed [label="commit scenario"];
  Draft -> Reverted [label="discard changes"];
  Reverted -> Draft [label="resume editing"];
  Committed -> Draft [label="new scenario"];
}
```

## State Descriptions

- **Draft**: Working copy with unsaved or invalid changes.
- **Validating**: Constraint & data integrity checks running (sync fast; escalate to async if heavy later).
- **Ready**: Clean state; eligible for simulation or commit.
- **Simulating**: Optimization engine executing (Phase 1 heuristic, later OR-Tools integration).
- **Committed**: Scenario persisted to storage (DB row or JSON file) with version tag.
- **Reverted**: User explicitly discarded current draft; last persisted state reloaded.

## Notes

- Validation provides structured errors (field + message) for future inline UI adornments.
- Long-running simulations should expose progress events (future EventBus integration).
- Committed state snapshot enables future diffing / version history.
