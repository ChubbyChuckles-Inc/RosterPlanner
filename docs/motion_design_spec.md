# Motion Design Specification (RosterPlanner)

## Purpose

Define consistent motion patterns that enhance comprehension and responsiveness without distracting users or harming performance.

## Core Principles

1. Intentional: Motion communicates state changes (enter, exit, emphasis) – never purely decorative.
2. Subtle by Default: Favor 140–200ms micro-animations; only escalate to 260ms+ for complex transitions.
3. Hierarchical: Primary context changes (view swap) > secondary (panel expand) > tertiary (button hover).
4. Performant: Avoid layout thrash; prefer opacity, transform, and cross-fade patterns.
5. Accessible: Respect OS / user preference for reduced motion (see Reduced Motion Strategy).
6. Interruptible: Users shouldn’t wait—animations can be skipped by subsequent interaction events.

## Duration Tiers

| Tier       | Token (motion.duration) | Range (ms) | Usage Examples                       |
| ---------- | ----------------------- | ---------- | ------------------------------------ |
| Instant    | instant                 | 60–90      | Focus ring, tap feedback             |
| Fast       | fast                    | 120–160    | Hover subtle scale, chip selection   |
| Base       | base                    | 180–220    | Dock panel slide, toast entry        |
| Slow       | slow                    | 240–280    | Dialog scale-in, complex list reflow |
| Deliberate | deliberate              | 320–380    | Onboarding step transitions          |

Actual token values sourced from `tokens.json` under `motion.duration`.

## Easing Curves

| Semantic   | Token      | Curve                          | Usage                      |
| ---------- | ---------- | ------------------------------ | -------------------------- |
| Standard   | standard   | cubic-bezier(0.4, 0.0, 0.2, 1) | Most UI enter/exit         |
| Accelerate | accelerate | cubic-bezier(0.4, 0.0, 1, 1)   | Quick fade out / shrink    |
| Decelerate | decelerate | cubic-bezier(0.0, 0.0, 0.2, 1) | Slide-in content           |
| Emphasized | emphasized | cubic-bezier(0.2, 0.0, 0, 1)   | Primary emphasize entrance |

## Pattern Catalog

1. Fade In (Opacity 0 -> 1): 140–200ms, standard easing.
2. Scale + Fade (0.95 -> 1, Opacity 0 -> 1): 160–200ms, emphasized easing for dialogs.
3. Slide + Fade (Y: 8px -> 0px, Opacity 0 -> 1): 180–220ms, decelerate easing for dropdowns.
4. Ghost Exit (Opacity 1 -> 0): 100–140ms, accelerate easing.
5. Reorder Morph (List item move): Use cross-fade + position animation (future optimization with constraint solver if needed).

## Reduced Motion Strategy

- Detect OS preference (if available) or user toggle in settings (future `settings.motionReduced` flag).
- When enabled: Disable non-essential translation/scale; keep instant opacity changes ≤ 80ms.
- Provide internal helper: `should_reduce_motion()` to gate animations.

## Implementation Guidelines

- Encapsulate animations in helper functions (future `gui/animation/animators.py`).
- Prefer QPropertyAnimation / QSequentialAnimationGroup; batch start to avoid stagger unless intentional.
- Avoid animating geometry directly; use wrapper QWidget with opacity/transform proxies where practical.

## Performance Considerations

- Coalesce multiple animations starting simultaneously to reduce layout recalculation.
- Throttle high-frequency animations (e.g., progress shimmer) with timer intervals ≥ 60ms.
- Use request batching for chained interactions (open + focus + highlight).

## Testing Approach

- Unit test timing helper functions (once implemented) for boundary clamping and reduced motion behavior.
- (Future) Visual diff or frame capture harness in dev mode.

## Future Extensions

- Spring physics easing presets for elastic transitions.
- Motion profiling overlay (frames timeline + jank detector).
- Adaptive duration scaling based on user perceived latency budget.

---

Document evolves with future ADR (e.g., ADR: Motion Architecture & Reduced Motion Policy).
