# Spec: Meetings, calls and where the time goes

Status: **accepted for the backlog** — scheduled as Phase 3 ("Calendar, meetings
& time"). Requested by the product owner on 2026-11-24.

## Why

Meetings silently consume the day. The goal is an honest answer to:

- How many hours did I actually have for focused work?
- How much time do I spend in meetings and calls — with whom, on what topic?
- Which of those were worth it?

## User stories

1. **Sync my Outlook calendar** so meetings appear in the tool without retyping.
2. **Mark a meeting as "not attending"** (or partially attended) so it doesn't
   count against my time — without changing anything in Outlook.
3. **Log a call that isn't in the calendar** — who, what, when, how long — in a
   few seconds, from quick capture or a "Log call" button, or with a running
   "In a call" timer.
4. **See where my time goes**: meeting vs. focus hours per day/week, time per
   person, time per topic, time per recurring series.
5. **Self-evaluate**: rate a meeting's value (1–5, optional note) right after it
   ends, then see value-per-hour and "meetings to reconsider".

## Calendar sources (in order of preference)

| Source | How | Pros | Cons |
|---|---|---|---|
| **Microsoft Graph** (Outlook / Microsoft 365) | Opt-in, OAuth *device-code* sign-in, read-only `Calendars.Read`, incremental `calendarView/delta` sync | Accurate, incremental, attendees and response status | Needs network to `graph.microsoft.com`; corporate tenants may require **admin consent** for an app registration |
| **ICS subscription URL** | Outlook "Publish calendar" → ICS link, polled periodically | No app registration; still automatic | Often disabled by company policy; less attendee detail; the URL is a secret |
| **.ics file import** | Export from Outlook, drag into the app | Works everywhere, fully offline | Manual; re-import needed |
| **Manual entry** | Log call / quick capture | Always available | Manual |

Design: one `CalendarSource` port with three adapters (Graph, ICS-URL, ICS-file).
The app stays fully usable with none configured. **This is the only feature that
makes outbound network calls**, it is off by default, and it talks to exactly one
configured host.

## Data model (new migration)

```
calendar_sources   id, kind (graph|ics_url|ics_file|manual), label, settings (json),
                   sync_cursor, last_synced_at, enabled
calendar_events    id, source_id, external_id, ical_uid, series_id,
                   title, start_at, end_at, all_day, timezone,
                   organizer, location, is_online, show_as (busy|tentative|free|oof),
                   my_response (accepted|tentative|declined|none),
                   is_cancelled, raw_hash, synced_at
                   UNIQUE (source_id, external_id)
event_participation event_id, status (attended|skipped|partial|unknown),
                   attended_minutes, value_rating (1..5), value_note, rated_at
                   -- user-owned: a re-sync NEVER overwrites this table
people             id, display_name, email (optional), team, notes
event_people       event_id, person_id, role (organizer|required|optional|logged)
topics             id, name, project_id (optional), goal_id (later)
event_topics       event_id, topic_id
```

- Manual calls are `calendar_events` with `source.kind = manual`, so all
  analytics treat synced and logged time identically.
- Synced data is a **read-only mirror**; everything the user decides
  (participation, rating, topics, people links) lives in separate tables, so
  sync is idempotent and never clobbers user input.
- Cancelled or deleted upstream events are marked, not removed, if they carry
  user data (rating, notes).
- Links: an event can link to notes (meeting notes) and create follow-up tasks
  (existing `links` table).

## Defaults and rules

- Declined → `skipped` automatically. Tentative → shown as "decide" until
  confirmed. Accepted → `attended` once it ends (editable).
- All-day, `free` and out-of-office entries don't count as meeting time.
  Focus-time blocks created in Outlook count as **focus**, not meetings.
- Overlapping meetings: time is counted once (union of intervals), with the
  overlap shown as a conflict.
- Working hours and a buffer are configurable (default 09:00–17:30, 15 % buffer).
- **Capacity becomes automatic**: `working hours − attended meetings − buffer`,
  feeding the existing Today capacity meter and overcommitment warning.

## UX

- **Today**: a compact timeline (rail or above the board) with meeting blocks;
  each block has *Attending / Not attending / Partial* and a ★ value rating after
  it ends. Free slots are visible for timeboxing tasks.
- **Log call** dialog: person (autocomplete, create on the fly), topic
  (autocomplete), start + duration or start/end, optional note → creates a
  manual event. Recent people/topics as one-click chips.
- **Quick capture grammar**: `call: Priya ~30m #retrieval ADR review`
  (`@14:00` optional start, default "ended just now").
- **"In a call" timer** in the rail: start → pick person/topic → stop logs it.
- **End-of-day review** gains "Rate today's meetings" (only unrated ones).
- **Insights** (Week / Insights views):
  - Meeting vs. focus hours per day and week, trend over weeks.
  - Time per person and per topic (top N, with share of meeting time).
  - Recurring series cost per month and average value rating.
  - "Meetings to reconsider": high time × low value, with a suggestion
    (shorten, make async, decline).
  - Value per hour by person/topic.

## Privacy and security

- Attendee names and emails are **other people's personal data**: stored only in
  `LOCAL_DATA_DIR`, never sent anywhere, excluded from AI context unless
  explicitly enabled, and deletable per person ("forget this person").
- OAuth refresh tokens / ICS URLs are secrets: stored in the OS keychain where
  available, otherwise encrypted in `LOCAL_DATA_DIR/config`, never logged,
  never exported in JSON exports.
- Read-only scope only; the tool never writes to Outlook.
- Demo workspace uses synthetic people and meetings.
- Threat model: see T14 in [threat-model.md](../threat-model.md).

## Acceptance criteria

- Re-running sync any number of times produces no duplicates and never
  overwrites participation, ratings, topics or people links.
- Toggling "not attending" updates capacity and meeting totals instantly
  (optimistic UI) and survives re-sync.
- A call can be logged in ≤ 10 seconds via keyboard only.
- Insights totals equal the union of attended intervals (tested with overlaps,
  time zones, DST changes and all-day events).
- With no calendar configured, everything else works unchanged.
- E2E tests: ICS import fixture → toggle attendance → log call → insights totals.

## Open questions for the product owner

1. Is your Outlook a **company Microsoft 365 tenant**? If yes, can you register
   an app (or get admin consent) for read-only calendar access? If not, ICS
   export/publish is the fallback.
2. Working hours and time zone; should travel days use the calendar's zone?
3. Should "focus" mean *time not in meetings* or only *explicitly tracked focus*
   (timer / timeboxed tasks)? Proposal: show both — "available" and "tracked".
4. Should people be grouped by team/organisation for the per-person view?
