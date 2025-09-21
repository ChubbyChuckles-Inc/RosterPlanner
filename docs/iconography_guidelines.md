# Iconography Guidelines (RosterPlanner)

## Purpose
Establish a consistent, maintainable icon system that supports theming, accessibility, and future plugin extensibility with minimal overhead.

## Design Principles
1. Consistency: All icons adhere to a 16px or 20px base grid (primary size 16px). Larger display icons (32px) scale proportionally.
2. Optically Balanced: Use a 1px stroke (or 1.25px optical if required) centered on the pixel grid to avoid blur at standard DPI.
3. Semantic Clarity: Icon shapes must communicate a single concept. Avoid metaphor overload.
4. Theming-Friendly: Icons are monochrome SVG paths using `currentColor` so they inherit from CSS/QSS color context.
5. Minimal Detail: Avoid micro-detail that won’t survive at 16px. Simplify silhouettes.
6. Motion Ready: Design forms that can gracefully animate opacity, scale (95%–100%), or stroke color without artifacts.
7. Accessibility: Do not rely on color alone; icons used as status indicators pair with shape or text when critical.
8. Extensibility: Registry-based discovery allows plugins to register new icons without modifying core files.

## Grid & Geometry
- Base grid: 16x16 units; artboard viewBox should be `0 0 16 16` for standard icons.
- Safe area: Maintain 1px padding where feasible (avoid crowding edges unless geometric necessity).
- Alignment: Use whole or half coordinates (.0 or .5) to maintain crisp rendering on typical scaling factors.

## Stroke & Fills
- Default stroke width: 1.25 (rounded), fallback 1 for simple shapes.
- Corners: Use round joins and round caps for a softer, modern aesthetic.
- Fill vs Stroke: Prefer stroke-based icons for adaptability; filled variants reserved for emphasis states.

## Naming Convention
- Kebab case (e.g., `refresh`, `open-folder`, `warning-triangle`).
- Status modifiers use suffix: `warning-triangle-filled`, `info-circle-outline`.

## File Organization
```
assets/
  icons/
    base/        # Core shipped icons
    plugin/      # Dynamically added at runtime (scan on startup)
```

## Theming
- Icons inherit color from surrounding widget via `currentColor`.
- Do not hardcode fills; if dual-tone needed, second tone uses 60% opacity of currentColor.

## Registration & Lookup
- Icons are registered via a central `IconRegistry` (see `gui/design/icons.py`).
- Lookup by symbolic name; registry resolves to on-disk SVG path.
- Plugins may call `register_icon(name, path)` during their activation.

## Versioning & Deprecation
- Provide metadata (added version, deprecated flag) for tooling to warn on deprecated usage.
- Deprecated icons remain for at least one minor release cycle.

## Testing Strategy
- Unit tests validate: registry load, duplicate prevention (unless override flagged), error on missing icon.
- Optional future visual regression: render sample icons and hash raster output.

## Performance Considerations
- Lazy load SVG contents only when first requested.
- Cache QIcon/QPixmap objects keyed by (name, size, mode, state, theme) in future extension.

## Future Extensions
- Multi-color palette mapping.
- Animated SVG segments (hover/active states).
- Automatic fallback chain (e.g., `warning-triangle` -> `warning` -> generic placeholder).

---
This document will evolve; record significant decisions in ADRs (e.g., ADR: Icon System Architecture).
