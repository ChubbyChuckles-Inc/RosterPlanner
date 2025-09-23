% Elevation Alignment Report (Milestone 5.10.37)

This report documents the current intended mapping of semantic elevation roles
to UI component categories and their corresponding numeric shadow levels.
It serves both as an audit of existing usage and as guidance for future
component development, ensuring consistent depth hierarchy and avoiding
visual ambiguity.

## 1. Semantic Roles Overview

| Role           | Enum Name        | Numeric Level | Typical Components                                                                 | Rationale                                                                 |
| -------------- | ---------------- | ------------- | ---------------------------------------------------------------------------------- | ------------------------------------------------------------------------- |
| Flat           | `FLAT`           | 0             | Base background panels, inline containers, simple labels                           | Neutral baseline; no depth emphasis.                                      |
| Secondary Dock | `SECONDARY_DOCK` | 1             | Logs, Stats, Detail, Planner, Recent docks                                         | Slight separation from background without overpowering primary structure. |
| Primary Dock   | `PRIMARY_DOCK`   | 2             | Navigation dock, Availability dock                                                 | Core structural pillars requiring stronger depth prominence.              |
| Floating Dock  | `FLOATING_DOCK`  | 3             | Detached (floating) docks                                                          | Elevated to indicate transient / movable state and focus priority.        |
| Overlay        | `OVERLAY`        | 4             | Future modal overlays, spotlight layers, command palette transient glass (planned) | Highest non-blocking prominence short of modal dialogs.                   |

Numeric levels are derived from token-driven or heuristic shadow specs in
`gui.design.elevation` and may scale differently if design tokens evolve.

## 2. Current Implementation Status

The following roles are actively applied within `MainWindow`:

- `PRIMARY_DOCK`: navigation, availability
- `SECONDARY_DOCK`: detail, stats, planner, logs, recent
- `FLOATING_DOCK`: dynamically applied when a dock is detached (see dock floating handlers)

The following roles are defined but not yet broadly used:

- `OVERLAY`: reserved for a future modal/overlay / live performance or focus overlay layer.
- Explicit `FLAT` application is implicit when no elevation role is set.

## 3. Alignment Checklist

| Check                                            | Status | Notes                                                          |
| ------------------------------------------------ | ------ | -------------------------------------------------------------- |
| All core docks assigned exactly one role         | Pass   | Applied at creation time in `_create_initial_docks`.           |
| Floating state upgrades elevation                | Pass   | Handled in `_on_dock_top_level_changed`.                       |
| No unintentional mixing of numeric shadow levels | Pass   | Only semantic API used.                                        |
| Overlay role placeholder defined                 | Pass   | Future integration pending overlay framework.                  |
| Tests reference role mapping                     | Pass   | `test_elevation_alignment_doc` ensures documentation coverage. |

## 4. Future Enhancements

1. Introduce an overlay manager applying `OVERLAY` for transient panels.
2. Add screenshot-based regression (Milestone 5.10.63) to hash shadow rendering.
3. Provide an in-app elevation debug toggle that annotates widgets with their role names visually.

## 5. Code Reference

```python
from gui.design.elevation import apply_elevation_role, ElevationRole

# Example: ensure a custom dock uses secondary docking elevation
apply_elevation_role(my_custom_dock, ElevationRole.SECONDARY_DOCK)
```

## 6. Rationale

Using semantic roles instead of raw numeric levels reduces design debt and
lowers the risk of inconsistent shadow usage as the UI grows. The mapping can
be rebalanced centrally without chasing scattered integers.

---

Generated as part of Milestone 5.10.37.
