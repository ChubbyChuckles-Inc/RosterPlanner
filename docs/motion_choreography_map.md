# Motion Choreography Map (RosterPlanner)

Milestone: 5.10.26

## Purpose

Provide a consistent, token‑driven sequencing model for how UI elements enter, exit, transform, and hand off focus. This expands on the high‑level principles in `motion_design_spec.md` by mapping concrete choreography patterns to component classes and interaction scenarios.

## Scope & Relationship to Motion Design Specification

The existing Motion Design Specification defines principles, duration tiers, and easing tokens. The choreography map answers: "When multiple things animate, in what order, with what offsets, and how do they coordinate?" It focuses on multi‑element transitions, not single micro‑animations.

## Core Choreography Principles

1. Hierarchical Cascade: Parent container establishes spatial context before children appear (e.g., dialog surface fades/scales first, then internal controls).
2. Temporal Compression: Total transition time rarely exceeds the slowest single animation tier (avoid additive delays); use overlapping phases.
3. Minimum Cognitive Latency: Staggers are subtle (20–40ms) unless emphasizing directional flow or list emphasis.
4. Deterministic Ordering: The same interaction always produces the same sequence (improves learned predictability & testability).
5. Accessibility Respect: Reduced motion mode collapses stagger + transforms, retaining only essential opacity changes.
6. Performance Budget: No choreography sequence should exceed 4 frames of layout/paint variance on baseline hardware.

## Taxonomy of Motion Events

| Category  | Description                                      | Examples                                            |
| --------- | ------------------------------------------------ | --------------------------------------------------- |
| Enter     | Element appears or is promoted to active context | Opening dock, new tab content, toast entry          |
| Exit      | Element leaves or is dismissed                   | Toast dismissal, dialog close, tab removal          |
| Transform | State change w/o creation/destruction            | Tab switch, density toggle, theme change fade       |
| Cascade   | Grouped sequence with offset                     | List items revealing, multi‑panel layout restore    |
| Replace   | One element swaps another                        | Skeleton -> real content, loading spinner -> result |

## Duration & Easing Mapping

Durations reference motion tokens (see `motion_design_spec.md`). Easing tokens selected by semantic intent.

| Scenario         | Phase              | Duration Token | Easing Token | Notes                                                     |
| ---------------- | ------------------ | -------------- | ------------ | --------------------------------------------------------- |
| Dock show        | Slide/Fade In      | base           | decelerate   | Slide (Y 12px->0) + opacity 0→1                           |
| Dock hide        | Fade Out           | fast           | accelerate   | Keep geometry stable; avoid slide to reduce layout        |
| Dialog open      | Scale+Fade Surface | slow           | emphasized   | Scale 0.95→1 + opacity 0→1; children delayed 40ms         |
| Dialog open      | Children Fade In   | fast           | standard     | Overlaps final 60% of surface animation                   |
| Toast entry      | Rise+Fade          | base           | decelerate   | Y 8px→0 + opacity 0→1                                     |
| Toast exit       | Fade/Slide Down    | fast           | accelerate   | Opacity 1→0; slight Y +4px                                |
| Tab switch       | Crossfade Outgoing | fast           | accelerate   | Outgoing lowers z & fades                                 |
| Tab switch       | Crossfade Incoming | fast           | decelerate   | Incoming fades after 20ms offset                          |
| Skeleton replace | Fade Skeleton Out  | fast           | accelerate   | Start once real content ready                             |
| Skeleton replace | Fade Content In    | fast           | standard     | Optional subtle scale 0.98→1 (disabled in reduced motion) |

## Sequencing Patterns

### 1. Parent-Child Entrance

Timeline (ms from t0):

- t0: Parent surface begins (e.g., dialog container scale+fade) [slow]
- t0+40: Key interactive children fade in (buttons, primary text)
- t0+80: Secondary/tertiary elements (helper text, decorative icons)

### 2. List Cascade (e.g., search results)

Up to first 8 items: stagger 24ms each (cap total additional delay ≈ 168ms). Items 9+ appear with batch fade (no stagger) to avoid elongated delays.

### 3. Tab Switch

Crossfade model (avoid slide to preserve spatial memory):

- Outgoing: opacity 1→0 (fast, accelerate)
- Incoming: starts 20ms after outgoing start, opacity 0→1 (fast, decelerate)
- Optional content scale suppressed by default (only for large view transitions > 75% surface change).

### 4. Skeleton -> Content

- Real data ready triggers parallel: skeleton opacity 1→0 (fast) & content opacity 0→1 (fast) with 16ms offset (content slightly later) to reduce perceived flash.
- Shimmer effect stops immediately at t0 (handled by future task 5.10.45).

### 5. Dock Layout Restore

When restoring saved layout: animate only newly shown docks (enter). Repositioning existing docks is instant (avoid layout thrash). Newly shown docks may stagger 32ms left-to-right or top-to-bottom.

## Stagger Strategy

Staggers are applied only when spatial grouping offers comprehension benefit. Default per-group offset: 24–32ms. Avoid nested staggers (child groups inside already staggered parent) except for large onboarding sequences (deliberate tier).

## Accessibility & Reduced Motion

Reduced motion mode collapses:

- All translation & scale transforms
- All staggers (set offset=0)
- Limits durations to `fast` or below
  Essential fades remain ≤ 120ms to preserve state clarity.
  Implementation hook: `should_reduce_motion()` (to be introduced in a later motion utilities milestone) gates animation branches. Choreography map treats this as a boolean switch for timing plan selection.

## Performance Budget & Metrics

Target ≤ 8ms main thread work per frame during active choreography. Long sequences must stream GPU‑accelerated properties (opacity, transform). Provide future instrumentation via motion profiling overlay (referenced in roadmap future task for motion profiling overlay).

## Testing Strategy

1. Presence Tests: This document's existence (implemented in `tests/test_motion_choreography_doc_presence.py`).
2. Future Automated Timing Tests: Validate computed timeline arrays from a forthcoming `MotionSequencePlanner` utility.
3. Reduced Motion Tests: Assert planner collapses offsets & transforms when flag set.
4. Visual Regression: Key sequences (dialog open, skeleton replace) captured as start→mid→end frames.

## Implementation Plan (Forward Looking)

1. Introduce `MotionPlanner` (maps scenario -> list[AnimationStep]).
2. Provide `AnimationStep` dataclass (target, property, start_ms, duration_ms, easing_token).
3. Integrate planner into existing animator helpers (dock, tab, toast) for consistency.
4. Add reduced-motion branch producing simplified step list.
5. Add profiling hook (collect aggregated duration & property counts).

## Component Mapping Snapshot

| Component         | Enter Pattern                 | Exit Pattern            | Transform Pattern                    |
| ----------------- | ----------------------------- | ----------------------- | ------------------------------------ |
| Dock Panel        | Slide+Fade (base, decelerate) | Fade (fast, accelerate) | Resize instant; drag feedback styled |
| Dialog            | Scale+Fade (slow, emphasized) | Fade (fast, accelerate) | Content updates crossfade            |
| Toast             | Rise+Fade (base, decelerate)  | Fade (fast)             | Position stack reorder instant       |
| Tab Content       | Crossfade (fast)              | Crossfade (fast)        | Density/theme apply fade overlay     |
| Skeleton Loader   | Immediate static              | Fade out (fast)         | Shimmer (future 5.10.45)             |
| Empty State Panel | Fade (fast)                   | Fade (fast)             | Subtle icon pulse optional           |

## Future Extensions

- Spring physics curve option (Milestone 5.10.27) extends planner with spring parameter struct (stiffness, damping, mass).
- Scroll-linked motion (Milestone 5.10.28) will add timeline normalization to scroll progress.
- Motion contrast tooling: highlight overlapping steps exceeding concurrency threshold.

---

Choreography map will evolve as motion utilities & planner abstractions are implemented in subsequent tasks.
