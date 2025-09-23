% Visual Integration Guide (Milestone 5.10.19)

# Visual Integration Guide

This guide explains how design tokens flow into runtime QSS and component styling.

## Token Sources

Design tokens (colors, spacing, radii, elevation, typography) are defined in the design system module and loaded via `load_tokens()`. They produce a structured object consumed by:

- `ThemeManager`: combines a base variant (default/high-contrast/brand-neutral) with dynamic accent derivation.
- Overlay presets (`theme_presets.py`): optional variant overlays (e.g., midnight, slate-light) applied post token flattening.
- `ThemeService`: augments semantics, applies contrast normalization, generates runtime QSS.

## Semantic Roles

Core semantic mappings (selected subset):

| Category   | Role      | Description                           |
| ---------- | --------- | ------------------------------------- |
| background | primary   | Root window background                |
| background | secondary | Elevated/secondary surface background |
| surface    | card      | Panel / card surfaces                 |
| text       | primary   | High-contrast foreground text         |
| text       | muted     | Secondary informational text          |
| accent     | base      | Primary interactive accent color      |
| accent     | hover     | Accent hover state                    |
| accent     | active    | Active/pressed accent state           |
| border     | medium    | Standard border / outline             |

## Runtime QSS Generation

`ThemeService.generate_qss()` draws from the active map to build a minimal, layered QSS snippet. The snippet is injected into `MainWindow` using the performance-instrumented `apply_theme_qss` utility, allowing style reapplication timing metrics.

Insertion strategy:

1. If an existing theme block is found (`/* THEME (auto-generated runtime) */`), it is replaced in-place preserving any developer custom additions before the marker.
2. Otherwise, the snippet is appended to the existing application style sheet.

## Contrast Normalization

To ensure accessibility, `ThemeService` enforces:

- `text.primary` contrast vs `background.primary` >= 4.5 (WCAG AA)
- `text.muted` contrast vs `background.primary` >= 3.0

If contrast is insufficient, fallback colors (#FFFFFF or #000000) are chosen based on higher computed ratio.

## Plugin Style Contract

Plugins must avoid hardcoded colors. The `PluginStyleContractPanel` provides a validation example. A validator scans widget QSS for hex values not present in the current theme mapping (with optional neutral whitelist) and reports violations.

## Adding a New Theme Variant

1. Add an overlay in `theme_presets.py` with minimal surface + text + accent + border keys.
2. Ensure high contrast between `text.primary` and `background.primary` (target >= 7.0 for best legibility if feasible).
3. Run `pytest -q tests/test_theme_variants.py` to validate contrast thresholds.

## Recommended Development Workflow

1. Modify tokens or overlay.
2. Run contrast + variant tests.
3. Launch GUI with `scripts/run_gui.ps1` and toggle variants from `View > Theme Variant`.
4. Use contrast check command (Command Palette: `Run Contrast Check`) for holistic verification.

## Avoiding Color Drift

Use token references or semantic roles when authoring component-specific QSS. Avoid raw hex literals in code or QSS (except within the central theme generation or explicitly whitelisted override layer). The drift detector and tests enforce this policy.

## Future Extensions

- Gradient & tonal ramp registry (Milestone 5.10.21)
- Glass surface adaptive blur (Milestone 5.10.22)
- Adaptive contrast tuning for dynamic accent changes (Milestone 5.10.24)

## Troubleshooting

| Symptom                              | Possible Cause                                    | Resolution                                                                                         |
| ------------------------------------ | ------------------------------------------------- | -------------------------------------------------------------------------------------------------- |
| Theme change has no visible effect   | QSS marker missing or exception during generation | Check logs for `[theme-style-apply]` entries and ensure ThemeService QSS generation succeeds       |
| Poor text readability in new variant | Insufficient contrast in overlay definition       | Adjust `text.primary` or darken/lighten `background.primary`; rely on normalization only as safety |
| Plugin panel shows disallowed colors | Hardcoded hex in plugin stylesheet                | Replace with semantic class or rely on theme-driven widget inheritance                             |

---

Document version: 1.0
