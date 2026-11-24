# Roadmap, open questions and technical debt

## Product bar

This is meant to be shown and shared. Every phase ships at a **premium
quality bar**, not just "feature complete":

1. **Instant** — interactions update optimistically; the server confirms in the
   background. Target: < 100 ms perceived response for every task/note action,
   first load < 200 KB gzipped (heavy editors load on demand).
2. **Keyboard-first, mouse-friendly, touch-capable** — every action has a
   shortcut; drag and drop works with pointer, touch *and* keyboard.
3. **Calm and dense** — one accent colour, hairline borders, restrained motion
   (respects reduced-motion), light and dark themes designed together.
4. **Forgiving** — undo instead of "are you sure?", version history instead of
   overwrites, backups before migrations.
5. **Honest** — no fake features: unbuilt areas say so with a clear preview.
   AI output is always labelled and reviewable.
6. **Shareable safely** — a synthetic demo workspace (`ppos demo`) so the
   product can be shown without exposing personal data.
7. **Verified** — each phase adds end-to-end tests in a real browser, not only
   unit tests.

See [design-system.md](design-system.md) for the visual language.

## Phases

| Phase | Scope | Status |
|---|---|---|
| 0 | Repository inspection, architecture, ADRs, threat model, data boundary | ✅ done |
| 1 | Tasks + Today + notes + local database | ✅ done |
| **1.5** | **Premium experience foundation** (design system, interaction model, demo workspace, e2e tests) | ✅ done — see below |
| 2 | Week view, sprints (2–3 weeks), weekly planning & review, capacity per week | ✅ done |
| 3 | **Calendar, meetings & time**: read-only Outlook (ICS) import, attendance per meeting and per series, call logging, time per person/topic, value ratings, automatic capacity — [spec](specs/meetings-and-time.md) | ✅ done |
| 3b | Timeboxing on a calendar timeline, recurrence expansion for tasks, installable app (PWA) | queued |
| 4 | Knowledge inbox: document ingestion, extraction/OCR, provenance, background jobs | **next** |
| 5 | Local LLM provider layer, prompt registry, writing studio, AI capture | |
| 6 | Context compiler + RAG; daily/weekly/sprint AI workflows | |
| 7 | Goals hierarchy, skills, performance frameworks, career evidence | |
| 8 | Insights/analytics, monthly / bi-monthly / quarterly / annual reviews | |
| 9 | Encryption at rest, local auth token, packaging, Postgres adapter, hardening | |
| 10 | Advanced agentic workflows and integrations | |

### Phase 1 delivered

Tasks (all fields from the brief except evidence links, which arrive with
goals/skills), subtasks, dependencies, drag/drop between states and days,
daily objective, capacity meter, top-3 priorities, overdue/due lists, roll-over,
end-of-day review, daily journal, notes with autosave + version history, ideas
inbox, projects/areas, generic links, quick capture grammar, full-text search,
command palette, audit log, migrations, backup/restore/export, boundary guard,
CI.

### Phase 1.5 delivered — premium experience foundation

**Design system** — tokens for light/dark, five dark palettes (Graphite,
Obsidian true-black, Midnight, Forest, Aubergine), six accent colours, comfortable and
compact density, Inter variable font bundled locally (no font CDN, keeping the
app fully offline), Lucide icon set, consistent primitives (buttons, chips,
segmented controls, sheets, dialogs, empty states).

**Interaction model**
- TanStack Query data layer with **optimistic updates** and rollback on error.
- dnd-kit drag and drop with drag overlay, drop highlighting, midpoint ordering
  (no renumbering), and **full keyboard support** (Space to pick up, arrows to
  move across columns, Space to drop).
- cmdk command menu (⌘K): fuzzy commands, live full-text results, theme switching.
- Quick capture with a **live parse preview** (chips for priority, estimate,
  date, project, tags) driven by the same server-side parser that saves.
- Sonner toasts with **Undo** for completion.
- `g`-chord navigation (`g t`, `g b`, `g n` …), `?` shortcut sheet, `/` search.

**Views redesigned** — Today (greeting, progress ring, capacity stat with
overcommitment alert, board + planning tray), new **Upcoming** (next 7 days),
Backlog (filter, sort, schedule shortcuts), Projects (cards with progress and
colours), Notes (TipTap rich-text editor that still stores **plain Markdown**,
formatting bar, tables, checklists, version-history sheet with non-destructive
restore), Settings (appearance, privacy & data, keyboard), and polished
"coming in Phase N" previews for unbuilt areas.

**Showcase & quality**
- `ppos demo` creates a separate workspace with realistic synthetic data and a
  visible "Demo data" badge.
- Responsive down to phone width with a floating mobile tab bar.
- Playwright end-to-end suite (mouse drag, keyboard drag, undo, capture preview,
  command menu, notes autosave, theming) running in CI against the demo
  workspace.
- Code-splitting: the editor loads only when Notes is opened.

**Bug found and fixed by the new e2e suite** — concurrent writes could fail with
`database is locked` (SQLite cannot upgrade a deferred read transaction while
another writer is active). Units of work now start with `BEGIN IMMEDIATE`; a
threaded regression test covers it.

### Phases 2 & 3 delivered — Week, Sprint, meetings & time

Plan: [plans/phase-2-3.md](plans/phase-2-3.md). Decisions from the product
owner: calendar import read-only and optional (purpose: recurring-meeting
overview), time zone default Europe/Berlin and changeable, working hours
default 08:00–17:00.

- **Workspace settings**: time zone, working hours, workdays, focus buffer,
  sprint length — "today" and all times follow the chosen zone.
- **Week**: Monday–Sunday board with per-day load vs. capacity and meetings,
  weekly objectives, sprint backlog docked on the right, drag between days
  (pointer + keyboard), roll unfinished work to next week, guided **weekly
  review** (completion, meeting share, estimate accuracy, meetings-vs-focus
  chart, reflection → plan next week).
- **Sprint**: goal, committed vs. stretch lanes, burndown with ideal line,
  scope changes after start, on-track indicator, add-from-backlog picker,
  completion with roll-over to the next sprint or backlog, sprint review.
- **Meetings & time**: read-only `.ics` import with recurrence expansion
  (exceptions, moved occurrences; cancelled / free / out-of-office skipped;
  attendee lists ignored); per-occurrence attendance (attend / partly / skip)
  and per-series "not attending"; value ratings; call logging via dialog,
  `call:` quick capture or the "In a call" timer; **automatic capacity**
  (working hours − attended meetings − buffer) with manual override;
  insights: meeting vs. focus per day, time with people, by topic, by recurring
  meeting, average value, "worth reconsidering".
- Two real bugs found by the new tests and fixed: nested transactions when
  reading settings (deadlock), and an invalid `step` on the call-duration input
  that blocked saving.

### Phase 2 plan — Week & Sprint (as planned; delivered above)

1. **Data**: `sprints` (goal, start/end, status) + `sprint_id` and
   `commitment` (committed | stretch) on tasks; weekly plan (three objectives,
   per-day capacity, notes); scope changes derived from the audit log.
   Migration `0002` with round-trip test.
2. **Week view**: seven day columns sharing the Today board components, sprint
   backlog docked on the right, drag between days (pointer + keyboard),
   per-day capacity bars, weekly objectives in the header.
3. **Sprint view**: goal, committed vs. stretch lanes, burndown chart (planned vs.
   remaining by day), risk/blocker list.
4. **Weekly review & planning**: a guided, step-by-step flow (review last week →
   roll over → set objectives → commit to the sprint), pre-filled
   deterministically from records.
5. **Sprint review**: commitment vs. completion, rollover with causes, lessons,
   carried into the next sprint.
6. **Tests**: domain invariants, migration round trip, e2e for week drag/drop
   and the review flow; screenshots in both themes.

### Phase 3 plan — Calendar, meetings & time (delivered; Graph sync deferred)

Full spec: [specs/meetings-and-time.md](specs/meetings-and-time.md).

1. **Calendar sources**: `.ics` file import and manual entries are built.
   Microsoft Graph sync and ICS subscription URLs are **deferred** — the owner
   only needs a read-only overview of recurring meetings, and file import needs
   no network access or IT approval.
2. **Attendance**: per-meeting *Attending / Not attending / Partial*, stored
   separately from the synced mirror so re-sync never overwrites it.
3. **Log a call** in seconds: dialog, quick capture (`call: Priya ~30m
   #retrieval ADR review`) or an "In a call" timer — person, topic, time.
4. **Automatic capacity**: working hours − attended meetings − buffer feeds the
   Today meter.
5. **Time insights**: meeting vs. focus hours, time per person, per topic, per
   recurring series; value rating (1–5) after each meeting; "meetings to
   reconsider". Basic charts ship in Phase 3; deeper trends in Phase 8.
6. **Timeboxing**: drag tasks into free calendar slots (moved to 3b).
7. Privacy: attendee data stays local, excluded from AI by default, deletable
   per person; tokens in the OS keychain.

### Premium items queued for later phases

| Item | Phase |
|---|---|
| More dark palettes ✅ shipped (Graphite, Obsidian, Midnight, Forest, Aubergine); a theme editor for custom palettes | 8 |
| Installable PWA (offline shell, app icon, standalone window) | 3 |
| Calendar timeline with drag-to-timebox | 3 |
| Natural-language dates in capture ("next Tuesday 3pm") | 3 |
| Bulk select & multi-drag on boards and lists | 2 |
| Undo for delete (soft delete with 30-day trash) | 2 |
| Inline `[[links]]` and backlinks between notes and tasks | 4 |
| Writing studio with side-by-side original / rewrite and diff | 5 |
| Streaming AI responses with source citations | 5–6 |
| Charts for insights (consistent palette, accessible in both themes) | 8 |
| Local auth token so the app can be safely opened from a tablet on the LAN | 9 |
| Signed desktop packaging | 9 |
| Visual-regression snapshots in CI | 2 |

## Requirements I'd challenge or that need an answer

1. **Model naming.** "Qwen 3.8 Flash Next 4-bit" is not a model id I can verify.
   The design makes the model pure configuration, so this does not block
   anything; the evaluation suite (Phase 5) should decide which local model is
   good enough per capability.
2. **PostgreSQL as primary.** For a single-user local app SQLite is simpler
   and safer to operate; Postgres stays available behind the same ports
   (ADR-0001). Please confirm, or tell me if multi-device access is a near-term need.
3. **Calendar source — answered: Outlook, read-only, optional.** Implemented as
   `.ics` import; live Graph sync only if it becomes necessary.
4. **Time zones — answered:** configurable, default Europe/Berlin. Still open:
   a day-start hour for late-night work.
5. **Capacity — answered:** working hours (default 08:00–17:00) − attended
   meetings − buffer (default 10 %), with per-day manual override.
6. **Encryption at rest.** Key management matters more than the cipher: a
   passphrase on startup vs OS keychain. OS full-disk encryption is the
   recommended baseline until then.
7. **Office mirror.** Licensing/ownership of the code when mirrored to an
   employer repository should be checked; the code contains nothing personal.
8. **Evidence semantics.** "Evidence" on tasks needs a precise definition
   (link to a note/document? measurable outcome?) before the career layer —
   otherwise reviews will be built on inconsistent data.
9. **Multi-device / mobile capture.** Quick capture from a phone is usually what
   makes or breaks adoption. Needs a sync or relay design that keeps the
   local-first guarantee (and the Phase 9 auth token).
10. **Showing it to others.** When you share it, use `ppos demo` (synthetic data)
    on your own machine or a screen share. Do not expose the server on a
    network until the Phase 9 auth token exists.

## Technical debt / known gaps

- Frontend types are hand-mirrored from the API; generate them from OpenAPI.
- Python dependencies are ranges, not a lockfile.
- `recurrence` is stored but not expanded (Phase 3).
- Typing `[ ]` *inside* an existing bullet list produces a literal `[ ]`
  (TipTap input-rule behaviour); start a checklist on a new line or use the
  toolbar.
- Deleting a task has no undo yet (confirm dialog instead) — soft delete queued.
- Week view on narrow screens scrolls horizontally; a single-day agenda layout
  for phones is queued.
- Insights range is up to 30 days in the UI (API supports a year); monthly /
  quarterly roll-ups arrive with Phase 8 reviews.
- No local auth token; API must stay on loopback (threat model T4/T5).
- Search ranks with bm25 only; no recency boost.
- The `ui` vendor chunk is ~140 KB gzipped; revisit if first load grows.
