# Pull Request

Provide a concise summary of the change and its purpose.

## Type of Change

- [ ] Feature
- [ ] Bug Fix
- [ ] Refactor
- [ ] Performance
- [ ] Documentation
- [ ] Test / CI
- [ ] Chore / Maintenance

## Related Issues / Milestones

Reference roadmap items (e.g. `0.25`) or issue numbers.

## Summary of Changes

Describe the key changes at a high level.

## Implementation Notes

Any design decisions, trade-offs, or notable patterns introduced.

## Validation

- [ ] Unit tests added / updated
- [ ] All tests passing locally (`pytest -q`)
- [ ] Manual QA performed (describe below)

### Manual QA Checklist

Describe manual checks performed (e.g. opened app, navigated to X, ran scrape, etc.)

## Usability & Design System Checklist (Milestone 0.25)

- [ ] No inline styles added (passes inline style lint)
- [ ] Color usage via tokens only (no new hardcoded hex values)
- [ ] Typography scales / hierarchy respected
- [ ] Interactive elements have accessible focus indication
- [ ] Motion durations use approved design tokens
- [ ] High contrast / dark mode considerations evaluated
- [ ] Responsive / reflow rules still valid (tested narrow width scenario)
- [ ] Notifications / errors use existing taxonomy (no new ad-hoc variants)
- [ ] Empty / error states align with registered templates
- [ ] Performance budgets considered (no egregious synchronous work on UI thread)

## Accessibility & Internationalization

- [ ] All user-facing strings externalized / ready for i18n
- [ ] Contrast levels acceptable (spot check)
- [ ] Keyboard navigation path preserved

## Dependency / Security Impact

- [ ] No new runtime dependencies
- [ ] If new dependency added, license reviewed and documented

## Screenshots / GIF (if UI changes)

Attach before/after or new UI visual references.

## Follow-Up Tasks

List any deferred items or TODOs created by this PR.

---

Generated as part of Milestone 0.25 (Usability heuristic checklist integration).
