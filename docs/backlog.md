# Backlog

**The single source of truth for feature requests.** Every request from the
product owner gets an ID here the moment it is made, and is never deleted —
only its status changes. Detailed specs live in `docs/specs/`, delivery notes
in `docs/roadmap.md`.

IDs: `R-` = request from the owner, `B-` = follow-up item spun off a request.

Status: `idea` → `planned` → `in progress` → `done` (or `deferred` / `declined`
with a reason).

| ID | Request (owner's words, condensed) | Requested | Status | Where |
|---|---|---|---|---|
| R-001 | Build the Personal Productivity & AI OS from the v2 brief (Phases 0–10) | 2026-11-24 | in progress | [roadmap](roadmap.md) |
| R-002 | Premium, showcase-quality look and feel; most advanced tools | 2026-11-24 | done (Phase 1.5) | [design-system](design-system.md) |
| R-003 | Track meeting time; productive-hours overview | 2026-11-24 | done (Phase 3) | [spec](specs/meetings-and-time.md) |
| R-004 | Outlook calendar: read-only import, overview of recurring meetings | 2026-11-24 | done (ICS import) · live sync deferred | [spec](specs/meetings-and-time.md) |
| R-005 | Disable calendar blocks I don't attend | 2026-11-24 | done (per occurrence + per series) | Meetings & time |
| R-006 | Add calls manually: person, purpose, time; time per person/topic; self-evaluate value | 2026-11-24 | done | Meetings & time |
| R-007 | More dark themes (I like dark) | 2026-11-24 | done (5 palettes) | Settings → Appearance |
| R-008 | Time zone changeable, default Central European | 2026-11-24 | done | Settings → Work & time |
| R-009 | Working hours flexible, aim 08:00–17:00 | 2026-11-24 | done | Settings → Work & time |
| R-010 | Plan and build Phases 2 (Week & Sprint) and 3 | 2026-11-24 | done | [plan](plans/phase-2-3.md) |
| R-011 | Layout adapts to 24″ and 32″ monitors like standard apps (font size) — *requirement* | 2026-11-24 | done | Settings → Appearance → Display size |
| R-012 | Prompt Book: book-like tool storing prompts/notes for AI, diary-style page turning, chapters/sections with multi-level hierarchy | 2026-11-24 | done | Prompt Book (`g k`) |
| R-013 | Improve prompts with local AI before sending to Copilot | 2026-11-24 | done (Ollama / OpenAI-compatible, local only; enable in `.env`) | Prompt Book → Improve with AI |
| R-014 | Some effects and emojis to make it more interesting — don't overdo it | 2026-11-24 | done (confetti for 3 big wins, emoji greetings/toasts, Settings toggle) | Settings → Celebrations |
| R-015 | Drag and drop of items from anywhere to anywhere | 2026-11-24 | done (boards, lists, sidebar, projects, Upcoming days, notes → Prompt Book; keyboard via task panel) | roadmap N4 |
| R-016 | Keep track of the backlog so feature requests are not lost | 2026-11-24 | done (this file) | — |
| R-017 | Configure the local LLM in the app (like Model Forensic): OpenAI-compatible endpoint e.g. `127.0.0.1:8080/v1`, model, key, reasoning effort, limits, Apply + Test connection | 2026-11-24 | done (presets, endpoint …/v1, auto-detected model, session or env-var key, reasoning effort, limits, Apply live, Test connection; local-only kept) | Settings → Local AI |
| R-018 | Task board across all work: Backlog, Planned, In progress, Completed (not only today) | 2026-11-25 | done (5 columns incl. Blocked, drag between states, filter, project, completed 7/30 days/all) | Task board (`g a`) |
| R-019 | Add meetings myself as separate items: one-off and recurring | 2026-11-25 | done (daily / weekdays / weekly on chosen days / monthly, every N, end on date or after N; edit changes the future only; end keeps history) | Meetings & time → New meeting |
| R-020 | Custom durations instead of a fixed 30 min | 2026-11-25 | done (time chip on every card with presets + free entry like 50 / 1h20 / 1.5h; `~50m` in quick add; any-minute meetings; default for unestimated tasks is a setting) | cards, task panel, Settings → Work & time |
| R-021 | Adding meetings manually (one-time or recurring) must be the obvious path, not hidden behind calendar import | 2026-11-27 | done (Add meeting on Today, Meetings header, Recurring tab, Meetings & calls tab, command menu; import is optional and collapsed) | Meetings & time, Today, ⌘K |
| R-022 | Add meetings from quick capture too | 2026-11-27 | done (`meeting:` / `mtg:` prefix: @day @HH:MM ~duration, repeats daily/weekdays/weekly/monthly/every N/every tue,thu, until/N times, with people, #topic; live preview) | Quick capture (`c`) |
| B-013 | Periodic reviews: monthly, bi-monthly, quarterly, annual — from own data, optional grounded AI draft | 2026-11-27 | done (numbers snapshot, your four sections, AI bullets must cite records and only use their numbers, finalize/reopen, copy as Markdown) | Reviews (`g v`) |
| B-014 | Insights: week-by-week trends from own records | 2026-11-27 | done (tasks per week, meetings vs focus, planned work done, estimate accuracy, work by project, meeting time by topic, table view) | Insights (`g i`) |
| B-015 | Assistant: ask questions answered from own records with citations; plan my day as an approvable proposal | 2026-11-27 | done (answers cite numbered sources, invalid/no citations flagged; plan ids not in your list dropped; nothing changes until you approve) | Assistant (`g j`) |
| B-016 | Hardening: local API token, Host/Origin checks, encrypted backups, locked dependencies, installer, installable app | 2026-11-27 | done (Phase 9) | README → Security, Quick start |
| B-017 | Repeating tasks that actually repeat (the RRULE field did nothing) | 2026-11-27 | done (repeat picker; completing creates the next occurrence; `every mon` in capture) | Task panel → Repeats, quick capture |
| B-018 | Full data export (only 9 of 38 tables were exported) | 2026-11-27 | done (tables discovered from the schema) | `ppos export` |
| B-019 | Undoable task deletes | 2026-11-27 | done (trash for 30 days, Undo in the message, Backlog → Recently deleted) | Task panel, Backlog |
| B-020 | AI drafts for the weekly review and sprint review | 2026-11-27 | done (same grounding as periodic reviews: cite records, unsupported bullets dropped; Use to insert) | Week → Review, Sprint → Complete |
| B-001 | Prompt Book: two-page spread view on very wide screens | 2026-11-24 | done (auto ≥ 1900 px, Spread/Single toggle) | Prompt Book |
| B-002 | Prompt Book: streaming AI output and "explain the changes" | 2026-11-24 | idea (from R-013) | — |
| B-003 | Optional emoji on projects and weekly objectives | 2026-11-24 | idea (from R-014) | — |
| B-005 | OCR for scanned PDFs (detected today as “Needs OCR”) — needs Tesseract on the machine | 2026-11-24 | planned (Phase 4b) | Knowledge |
| B-006 | Word (.docx) import | 2026-11-24 | planned (Phase 4b) | Knowledge |
| B-007 | Extract facts (responsibilities, achievements, competencies) with provenance using the local model | 2026-11-24 | done (verbatim-quote grounding, accept/reject) | Knowledge → Facts from this document |
| B-009 | Career view: accepted facts mapped to framework levels and competencies | 2026-11-24 | done (levels from framework facts, user-confirmed evidence links, coverage as hypothesis, gap → task) | Career (`g c`) |
| B-010 | Career suggestions that understand synonyms (semantic matching) | 2026-11-24 | idea (from B-009; needs B-008) | — |
| B-011 | Goals hierarchy linked to career expectations; skills matrix | 2026-11-24 | done (year → quarter → month goals with computed progress and pace, linked to tasks, projects, expectations and skills; skills with rating history, targets, evidence, gap → goal) | Goals (`g g`), Skills (`g l`) |
| B-012 | Add career evidence by hand (statement + quote from a document, or your own note) so Career works without AI | 2026-11-24 | done (saved as a “My evidence note” in Knowledge, accepted and labelled “Your note”; linkable from Career and Skills) | Career / Skills → Link evidence |
| B-008 | Semantic (vector) search alongside keyword search | 2026-11-24 | done (local /v1/embeddings, stored on disk, fused with keyword search by reciprocal-rank fusion; optional) | Assistant (`g j`), Settings → Local AI |
| B-004 | Drag tasks onto projects, sprint and Upcoming days; notes into the Prompt Book | 2026-11-24 | done | sidebar Today / Backlog / Sprint / Prompt Book, project cards, Upcoming days |

## Deferred / declined, with reasons

| ID | Item | Reason |
|---|---|---|
| D-001 | Live Microsoft Graph (Outlook) sync | Owner only needs a read-only overview; file import needs no network or IT approval. Revisit on request. |
| D-002 | PostgreSQL as primary database | SQLite fits single-user local-first better (ADR-0001); Postgres stays possible behind the same ports. |

## How requests are handled

1. New request → add a row here immediately (ID, condensed wording, date, `idea` or `planned`).
2. Non-trivial items get a section in `roadmap.md` or a spec in `docs/specs/`.
3. When delivered, status becomes `done` with a pointer to where it lives.
4. Nothing is removed; scope changes are recorded as new rows or in the
   deferred table with the reason.
