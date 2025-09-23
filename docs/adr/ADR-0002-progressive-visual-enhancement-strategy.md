# ADR-0002: Progressive Visual Enhancement Strategy

Status: Accepted  
Date: 2025-09-23  
Milestone: 5.10.20  
Related: ADR-0001 (Ingestion Lifecycle), Visual Integration Guide

## Context

The GUI incorporates a growing set of visual polish features (animated docks, glass surfaces, gradient ramps, adaptive blur, skeleton shimmer, contrast overlays). Each enhancement can introduce runtime cost (layout / paint overhead, GPU composition, memory for offscreen buffers). We must balance accessibility & aesthetics with deterministic responsiveness and predictable resource usage.

We already have: design tokens (color/spacing/typography), dynamic theme overlays, performance instrumentation for style reapplication, and focus/contrast validation utilities.

## Problem

Uncoordinated introduction of advanced visual effects risks:

- Regressing interaction latency (>120ms budget) or style apply time (>50ms guard).
- Making high-contrast / reduced-motion users experience unnecessary motion or translucency.
- Increasing complexity for plugin developers who must not depend on ephemeral visual affordances.

## Forces / Constraints

| Force            | Description                                                                                   |
| ---------------- | --------------------------------------------------------------------------------------------- |
| Accessibility    | Must respect reduced motion & high contrast preferences.                                      |
| Performance      | Maintain <16ms/frame for animated interactions; avoid jank under typical workloads.           |
| Maintainability  | Keep feature flags simple & centrally discoverable.                                           |
| Testability      | Logic paths (enabled/disabled) must be asserted via unit/integration tests.                   |
| Plugin Stability | Plugins may not rely on non-token visual gradient/blur layers unless part of public contract. |

## Decision

Adopt a structured progressive enhancement ladder with explicit opt-in flags for non-essential visuals.

1. Baseline Layer (Always On): tokens, contrast normalization, static QSS, focus ring, high-contrast variant, density modes.
2. Tier A (Default On, Auto-Disabled by Reduced Motion): micro easing animations (dock show/hide, tab transitions), non-looping skeleton placeholder fade.
3. Tier B (Opt-In via Settings / Env Flag): glass surfaces (blur), gradient backgrounds, shimmer skeleton effect, ambient color shift, scroll-linked fades.
4. Tier C (Developer / Experiment): ambient drift, spring physics, layout shift monitor overlay, theme A/B harness.

Feature gating mechanism:

- Central `VisualFeatures` dataclass (future) or settings service with boolean fields.
- Environment variable overrides: `RP_DISABLE_TIER_A`, `RP_ENABLE_TIER_B`, `RP_ENABLE_TIER_C`.
- Command Palette actions to toggle Tier B/C (dev mode only) publishing events.

Performance contract additions:

- Each Tier B/C feature must include instrumentation (duration or frame delta) with a warning log if threshold exceeded.
- New effects must degrade gracefully (no-op) when disabled.

## Alternatives Considered

| Option                              | Rationale for Rejection                                         |
| ----------------------------------- | --------------------------------------------------------------- |
| Always enable everything            | Risk of unpredictable performance in low-resource environments. |
| Per-component bespoke flags         | Fragmented config surface; higher cognitive load.               |
| Dynamic adaptation only (heuristic) | Harder to test; risk of unstable user experience.               |

## Implementation Sketch

- Introduce `visual_features.py` with an immutable snapshot object produced at bootstrap.
- Provide `rebuild_features(settings_service)` to recompute after settings change.
- Emit `GUIEvent.VISUAL_FEATURES_CHANGED` upon toggle.
- QSS generation remains purely token-based; advanced visuals attach via specialized widgets (e.g., glass panel wrapper) that check feature flags.

## Test Strategy

- Unit tests verifying feature gating logic under combinations of env vars and settings.
- Integration test future: ensure disabling Tier A (via forced reduced motion scenario) removes animation durations (time budget <5ms path).

## Migration / Rollout

- Start with stub flags referencing existing animations (Tier A) and add Tier B placeholders returning False until implemented.
- Document flags in Developer README and Visual Integration Guide (appendix update).

## Risks & Mitigations

| Risk                                      | Mitigation                                                                            |
| ----------------------------------------- | ------------------------------------------------------------------------------------- |
| Flag sprawl                               | Single dataclass & documented naming convention.                                      |
| Hidden performance regression             | Mandatory instrumentation & thresholds.                                               |
| Plugin misuse of Tier C experimental APIs | Keep experimental modules under `gui/experiments/` and exclude from public `__all__`. |

## Consequences

Positive: Predictable layering, easier audits, accessible defaults.  
Negative: Slight upfront complexity adding gating boilerplate.

## Future Work

- Add CLI diagnostic: summarize enabled visual features & performance counters.
- Extend contrast heatmap overlay (Milestone 5.10.35) to leverage feature gating path.

## Status Footnote

Accepted and scheduled—foundational gating utilities to be added before implementing any Tier B feature tasks (glass, gradients).
