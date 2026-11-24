# Roadmap, open questions and technical debt

## Phases

| Phase | Scope | Status |
|---|---|---|
| 0 | Repository inspection, architecture, ADRs, threat model, data boundary | ✅ done (repo was empty) |
| 1 | Tasks + Today + notes + local database | ✅ done — see below |
| 2 | Week view, sprints (2–3 weeks), backlog grooming, capacity per week | next |
| 3 | Calendar import / timeboxing, recurrence expansion | |
| 4 | Knowledge inbox: document ingestion, extraction/OCR, provenance, job queue | |
| 5 | Local LLM provider layer, prompt registry, writing assistant, AI capture | |
| 6 | Context compiler + RAG; daily/weekly/sprint AI workflows | |
| 7 | Goals hierarchy, skills, performance frameworks, career evidence | |
| 8 | Analytics, monthly / bi-monthly / quarterly / annual reviews | |
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

### Phase 2 plan (next)

1. `sprints` table (goal, start/end, status) + `sprint_id` / `commitment`
   (committed | stretch) on tasks; scope-change events derived from the audit log.
2. Weekly plan entity (objectives, capacity per day, notes); Week view with seven
   day columns and the sprint backlog on the right; drag between days.
3. Weekly review + planning workflow; sprint review (committed vs completed,
   rollover, causes, lessons).
4. Tests: sprint invariants, scope-change accounting, migration 0002 round trip.

## Requirements I'd challenge or that need an answer

1. **Model naming.** "Qwen 3.8 Flash Next 4-bit" is not a model id I can verify.
   The design makes the model pure configuration, so this does not block
   anything; the evaluation suite (Phase 5) should decide which local model is
   good enough per capability.
2. **PostgreSQL as primary.** For a single-user local app SQLite is simpler
   and safer to operate; Postgres stays available behind the same ports
   (ADR-0001). Please confirm, or tell me if multi-device access is a near-term need.
3. **Calendar source.** Which calendar(s)? ICS file/URL import is simple and
   fully local; Google/Outlook need OAuth and network access, which conflicts
   with the local-only posture. Needed before Phase 3.
4. **Time zones and "day".** Days are the user's local calendar day; travel and
   late-night work need a rule (e.g. a configurable day-start hour).
5. **Capacity definition.** Phase 1 uses a manually set focus capacity per
   day. With calendar import it should become working hours − meetings −
   buffer. Confirm the default buffer.
6. **Encryption at rest.** Key management matters more than the cipher: a
   passphrase on startup vs OS keychain. OS full-disk encryption is the
   recommended baseline until then.
7. **Office mirror.** Licensing/ownership of the code when mirrored to an
   employer repository should be checked; the code contains nothing personal.
8. **Evidence semantics.** "Evidence" on tasks needs a precise definition
   (link to a note/document? measurable outcome?) before the career layer — 
   otherwise reviews will be built on inconsistent data.
9. **Multi-device / mobile capture.** Not in the brief, but quick capture from
   a phone is usually what makes or breaks adoption. Would need a sync or
   relay design that keeps the local-first guarantee.

## Technical debt / known gaps

- Frontend types are hand-mirrored from the API; generate them from OpenAPI.
- No frontend component or end-to-end tests in CI yet (a Playwright smoke run
  was done manually); add a Playwright job.
- Python dependencies are ranges, not a lockfile.
- `recurrence` is stored but not expanded (Phase 3).
- Markdown is edited as plain text; no rich-text editor or rendered preview yet.
- No local auth token; API must stay on loopback (see threat model T4/T5).
- Search ranks with bm25 only; no recency boost.
