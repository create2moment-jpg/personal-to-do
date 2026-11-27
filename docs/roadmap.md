# Roadmap, open questions and technical debt

> All feature requests and their status are tracked in [backlog.md](backlog.md).

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
| 3c | Task board across all states (R-018), meetings you create incl. recurring series (R-019), any-minute durations and a configurable default for unestimated tasks (R-020) | ✅ done |
| N1–N4 | Large-monitor layout (24″/32″), Prompt Book with local-AI improvement, delight effects, drag and drop everywhere — see "Next features requested by the owner" | ✅ done |
| 4 | Knowledge inbox: document ingestion, extraction, provenance, background jobs | ✅ done incl. AI fact extraction (B-007) — OCR and .docx queued (B-005, B-006) |
| 5 | Local LLM provider layer, prompt registry, writing studio, AI capture | started — provider layer (any OpenAI-compatible local server, configured live in Settings → Local AI, R-017), prompt templates and output validation shipped |
| 6 | Context compiler + RAG; daily/weekly/sprint AI workflows | |
| 7 | Goals hierarchy, skills, performance frameworks, career evidence | ✅ done — Career view (B-009), Goals and Skills matrix (B-011) |
| 8 | Insights/analytics, monthly / bi-monthly / quarterly / annual reviews | ✅ done — Reviews (B-013) and Insights (B-014) |
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

### Phase 4 delivered — Knowledge inbox (core)

- Upload PDF / .txt / .md (drag anywhere onto Knowledge, up to 50 MB); type is
  checked by content, not name; SHA-256 de-duplication.
- Originals stored untouched and content-addressed in
  `LOCAL_DATA_DIR/documents/` (`0600`), served back sandboxed.
- Background pipeline (in-process worker, resumed after restarts):
  checksum verify → per-page extraction (pypdf) → heading/section detection →
  chunking that never spans pages → FTS index. Scanned PDFs are flagged
  "Needs OCR"; failures are recorded on the document, never crash the app.
- Every chunk carries provenance: document, page, section, character offsets,
  extractor version. Re-index one or all documents when the extractor changes.
- Search inside documents (Knowledge and ⌘K) with page citations; the reader
  jumps to and highlights the cited passage.

### Phase 4b delivered — AI fact extraction (B-007)

- Local model reads each passage with the versioned template
  `documents.extract_facts@v1` and proposes facts of seven kinds
  (responsibility, achievement, competency, strength, development area, goal,
  level expectation).
- **Grounding guard:** every fact must carry a quote that occurs verbatim in
  its passage; anything else is dropped and counted ("n dropped") — the model
  cannot introduce achievements that are not in the document.
- Provenance on every fact: document, chunk, page, section, model, prompt
  template, extractor version. Bounded runs (≤ 60 passages) in the background
  with live progress; re-runs replace only unreviewed proposals and never
  re-propose a fact you already accepted or rejected.
- Facts are proposals: accept / reject in the document; only accepted facts
  feed career evidence (Phase 7, B-009). The quote can never be edited.
- Chunking now starts a new passage at every heading (chunk:v2) so framework
  levels and review sections are cited separately.

### Phase 8 — Reviews and Insights (B-013, B-014)

- **Reviews** for a month, two months, a quarter or a year. A snapshot of the
  numbers comes from your own records (tasks, meetings, sprints, goals, skills,
  evidence, daily/weekly review notes); you write highlights, challenges,
  learnings and next focus. Finalize freezes the numbers.
- **Grounded AI drafts** (optional, local model): every bullet must cite the
  numbered items of the snapshot and may only use numbers that appear in what
  it cites; other bullets are dropped and listed with the reason. Text is only
  inserted when you press *Use*.
- **Insights**: 8 / 12 / 26-week trends — tasks completed, meetings vs time free
  for focus, share of planned work done (days not yet over don't count),
  estimate accuracy against 100%, work by project, meeting time by topic, and
  every number as a table. Charts follow the validated palette and data-viz
  rules (one axis, legends for two series, hover tooltips).

### Phase 7 — Goals and Skills (B-011)

- **Goals:** year → quarter → month, each sub-goal inside its parent's period.
  Progress is computed and explained: from linked tasks (directly or through a
  linked project), from a number you track (e.g. 3 of 4 talks), from your own
  estimate, or as the average of sub-goals. A pace hint compares progress with
  the share of the period that has passed (ahead / on track / behind) and is
  labelled as a hint. Goals link to career expectations (shown in Career) and
  to skills; drag a task onto a goal to link it; deleting a goal keeps its
  tasks and sub-goals.
- **Skills:** self-rated 1–5 (Aware → Expert) with a full history and a
  three-month trend, a target and gap, evidence from accepted facts (suggested
  by shared words, confirmed by you), accepted competencies offered as new
  skills, and "Make it a goal" that creates a linked quarter goal.
- Demo workspace ships goals and skills so both views are populated.

### Phase 7 started — Career view (B-009)

- **Framework:** accepted *level expectation* facts from a framework document
  become rows grouped by level (L4, L5, …; the level is read from the
  passage's section heading). Expectations can also be added by hand.
  Removing a framework row rejects its fact so it does not come back.
- **Evidence:** only *accepted* achievements, responsibilities,
  competencies and strengths. Development areas and goals are never
  evidence. Every evidence item shows its verbatim quote and opens the
  source passage.
- **Linking is always the user's act.** Suggestions are explainable word
  overlap (a small, predictable stemmer; at least two shared terms), shown
  with the shared words. Nothing is linked automatically and no model is
  involved, so it works with AI off.
- **Coverage per level is labelled as a hypothesis** ("Evidence covers 1 of 2
  expectations") and is never presented as readiness or a promotion verdict.
  Evidence that is later rejected stops counting immediately.
- **Gaps → action:** an expectation without evidence has *Create a task to
  build evidence* (tagged `career`).
- Demo workspace ships hand-curated accepted facts, with quotes checked
  against the demo documents, so the view is populated without a local model.
- Next in Phase 7: goals hierarchy linked to expectations; skills matrix;
  AI-drafted (grounded, user-approved) mapping suggestions as an option.

### Next features requested by the owner (queued after the current target topics)

Recorded 2026-11-24. Order reflects value vs. effort; each ships at the
product bar above.

**N1 — Large-monitor layout (24″ and 32″)** · *requirement* · ✅ done
- Goal: behave like standard desktop apps across resolutions — 24″ (1920×1080
  or 2560×1440) and 32″ (2560×1440 or 3840×2160 at 150–200 % OS scaling).
- Fluid type and spacing scale (`clamp()`-based root size) so text stays a
  comfortable reading size instead of shrinking on high-resolution screens;
  respects the OS/browser zoom rather than fighting it.
- Content widths capped for reading (notes, settings, reviews), while boards
  (Today, Week, Sprint) use the extra width: wider columns, the right rail and
  sprint backlog shown side by side, more days/columns visible at once.
- Breakpoints added above the current ones (≈1680 px, ≈2200 px, ≈2800 px).
- A "Display size" setting (Auto / Compact / Comfortable / Large) as an
  override, next to the existing density setting.
- Acceptance: Playwright screenshots at 1920×1080, 2560×1440 and 3840×2160
  (device scale 1 and 2) with no clipped text, no horizontal page scroll,
  and primary text ≥ 13 px effective.
- Delivered: all sizes are `rem`; root size is 14 px up to ~2200 CSS px and
  grows to 18 px on 32″ 4K at 100 % scaling (OS scaling at 150–200 % keeps
  14 px, as Windows already enlarges); wider sidebar/rail and page widths
  above 1800 px; Display size override S / M / L / XL. Verified at 1600,
  1920×1080, 2560×1440, 3840×2160 @1× and @2× with no horizontal overflow.

**N2 — Prompt Book (writing desk for AI prompts)** · ✅ done (spread view → backlog B-001)
- A book-like tool for notes and messages you give to AI assistants: every
  prompt you write is stored, versioned and searchable.
- **Multi-level hierarchy**: Book → Chapter → Section → Page (arbitrary
  depth via a parent tree), drag to reorder or move pages between chapters,
  table of contents sidebar.
- **Diary view**: one page at a time with a page-turn transition (respecting
  reduced motion), ←/→ to flip pages, a date per page, and a spread view on
  wide screens.
- **Improve with local AI** (needs Phase 5 provider): side-by-side original
  vs. improved prompt with a diff; choose a style (clearer, more specific,
  add context, add constraints/output format); the original is never
  overwritten; both versions are kept.
- **Send to Copilot**: one click copies the chosen version to the clipboard
  (no direct Copilot integration — nothing leaves the machine automatically),
  and records when/where it was used plus an optional "did it work?" rating.
- Reusable templates and variables (e.g. `{{repo}}`, `{{goal}}`), tags, links
  to tasks/projects.
- Data: `books`, `book_nodes` (tree with position), `prompt_versions`
  (original / improved, model + prompt-template version for AI output).
- Before Phase 5 lands, the book is fully usable without AI; the "Improve"
  button explains that it activates with the local model.

**N3 — Delight, in moderation** · ✅ done (project/objective emoji → backlog B-003)
- Small, meaningful moments: a light confetti burst when all three top
  priorities are done or a sprint completes; a "day closed" animation after
  the end-of-day review; subtle springy drop on drag and drop.
- Optional emoji for projects, notes chapters and weekly objectives
  (picker, never required); streak and celebration messages with a little
  personality.
- Rules: max one celebration per event type per day, ≤ 800 ms, never blocks
  input, respects `prefers-reduced-motion`, and a Settings toggle
  ("Celebrations: on / subtle / off").

**N4 — Drag and drop everywhere** · ✅ done
- Today: drag between board, backlog and overdue already works; Week: between
  days and sprint backlog; Sprint: lanes via buttons.
- Extend to: drag tasks onto projects (sidebar or project cards), onto the
  sprint from any list, between Upcoming days, notes into Prompt Book
  chapters, and pages between chapters — all with keyboard equivalents.

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
- Career suggestions use word overlap only; synonyms ("mentored" vs "coached")
  are missed until semantic search (B-008) is available.
