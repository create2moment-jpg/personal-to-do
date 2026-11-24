# Plan: Phase 2 (Week & Sprint) + Phase 3 (Calendar, meetings & time)

Decisions from the product owner (2026-11-24):

- Calendar import is **read-only and optional**; its purpose is an overview of
  **recurring meetings**. Everything else is added manually.
- Time zone configurable, default **Europe/Berlin** (Central European Time).
- Working hours flexible, default **08:00–17:00**.
- Build both phases; the owner tests the final product.

## Scope

### Phase 2 — Week & Sprint
1. **Workspace settings** stored in the database (time zone, working hours,
   workdays, buffer %, default sprint length), editable in Settings. "Today" is
   computed in the configured time zone.
2. **Sprints**: name, goal, start/end (default 14 days, 7–28 allowed), status
   planned → active → completed; at most one active sprint; tasks get
   `sprint_id` + `commitment` (committed / stretch). Scope changes after the
   sprint starts are recorded.
3. **Sprint view**: goal, progress, committed vs. stretch lanes, burndown
   (remaining estimate per day vs. ideal), scope-change list, sprint review
   (committed vs. completed, added mid-sprint, rolled over, lessons) and
   completion with roll-over to the next sprint or the backlog.
4. **Week view**: Monday–Sunday columns with tasks, per-day load vs. capacity
   and meeting time, three weekly objectives, sprint backlog docked on the
   right, drag between days (pointer + keyboard).
5. **Weekly review**: one guided page — numbers (planned vs. done, rollover,
   estimate vs. actual, meeting hours), objectives check, reflection, next
   week's objectives.

### Phase 3 — Calendar, meetings & time
1. **ICS import** (read-only, file upload; Outlook → File → Save calendar or a
   published calendar). Recurring events are expanded for a window
   (−30 / +90 days). Re-import is idempotent and never overwrites what the user
   set (attendance, rating, topic, notes). Microsoft Graph sync stays in the
   backlog (not needed).
2. **Meetings** with attendance per occurrence (attended / skipped / partial)
   and per **series** ("I'm not attending this recurring meeting").
3. **Log a call** manually: people, purpose, topic, start, duration — via a
   dialog, quick capture (`call: Priya / ADR review ~30m #retrieval`) or the
   "In a call" timer.
4. **Automatic capacity**: working hours − attended meetings − buffer (manual
   override per day still possible).
5. **Time insights**: meeting vs. focus hours per day/week, time per person,
   per topic, per recurring series (hours/month), value ratings and
   "meetings to reconsider".
6. **Today / Week integration**: today's meetings with attendance toggles;
   meeting time per day in the Week view.

## Data (migration 0002)
`workspace_settings`, `sprints`, `sprint_scope_events`, `weekly_plans`,
`tasks.sprint_id` + `tasks.commitment`, `daily_plans.capacity_mode`,
`people`, `topics`, `meeting_series`, `meetings`, `meeting_people`,
`calendar_imports`. Imported fields and user fields live in different columns;
re-import updates only imported columns.

## Definition of done
Domain + service + API tests, migration round trip, Playwright e2e for week
drag, sprint flow, ICS import → skip series → capacity change, call logging;
demo workspace extended with a sprint, a weekly plan, recurring meetings and
calls; docs and roadmap updated.
