# Design system

The visual and interaction language for Personal OS. Source of truth:
`apps/web/src/styles.css` (tokens + primitives) and `apps/web/src/components/`.

## Principles

- **Calm density.** Information-rich screens without noise: neutral surfaces,
  hairline borders (`--border`), one accent colour, colour reserved for meaning
  (priority, status, warnings).
- **Content first.** Chrome recedes; titles use tight tracking and weight, metadata
  is small and muted.
- **Motion with purpose.** Motion explains change (a card moving, a sheet
  arriving), never decorates. 120–200 ms, ease-out; springs for panels. Reduced
  motion is respected globally (`MotionConfig reducedMotion="user"`).
- **Light and dark are equals.** Every token has both values; screenshots of
  new work are checked in both.

## Tokens

| Group | Tokens |
|---|---|
| Surfaces | `--bg`, `--bg-sunken`, `--surface`, `--surface-2`, `--surface-hover` |
| Text | `--text`, `--text-2` (secondary), `--text-3` (muted) |
| Lines & depth | `--border`, `--border-strong`, `--shadow-sm`, `--shadow`, `--shadow-lg` |
| Accent | `--accent`, `--accent-2` (hover), `--accent-soft` (tints), `--accent-text` |
| Semantic | `--red`, `--orange`, `--yellow`, `--green`, `--blue`, `--purple` |
| Priority | `--p1` red · `--p2` orange · `--p3` blue · `--p4` muted |
| Radius | `--radius-xs` 5 · `--radius-sm` 7 · `--radius` 10 · `--radius-lg` 14 · `--radius-xl` 18 |
| Rhythm | `--row` (nav/list row height), `--space` (density multiplier) |

Theme, accent (`indigo`, `violet`, `blue`, `teal`, `amber`, `rose`) and density
(`comfortable`, `compact`) are attributes on `<html>`: `data-theme`,
`data-accent`, `data-density`. They are UI preferences stored in the browser
only (never personal content).

## Typography

Inter Variable, bundled locally via `@fontsource-variable` (no font CDN — the
app works fully offline). Body 14 px / 1.45, slight negative tracking.
Page titles 26–30 px, weight 650–680, tracking −0.03 em. Numbers that change use
tabular figures (`.tnum`).

## Status & priority language

| Status | Mark |
|---|---|
| Planned | hollow ring, muted |
| In progress | half-filled ring, accent |
| Blocked / waiting | hollow ring, orange |
| Done | filled dot, green; title struck through and muted |

Priority shows as a flag (P1–P3) and colours the task checkbox ring. P4 shows
nothing — absence of priority is the default, not a label.

## Components

`Dialog` (centred, blurred backdrop), `Sheet` (right slide-over), `Kbd`/`Keys`,
`StatusDot`, `EmptyState` (icon + title + one helpful sentence), `ProgressRing`,
`TaskCard` / `SortableTaskCard`, segmented control, chips, filter chips.

## Interaction rules

- Every action is keyboard reachable; shortcuts are shown where the action lives.
- Prefer **undo** over confirmation. Confirmation only for destructive,
  non-undoable actions (until soft delete lands).
- Updates are optimistic; errors roll back and explain themselves in a toast.
- Empty states teach the next action (e.g. "Capture something with C").
- Unbuilt features are clearly labelled "Soon" with an honest preview — no dead
  buttons.

## Checklist for new UI

- [ ] Works in light and dark, all six accents, both densities.
- [ ] Keyboard path exists and is discoverable.
- [ ] Loading, empty and error states designed.
- [ ] No horizontal scroll at 390 px width.
- [ ] Covered by a Playwright test of the main interaction.
