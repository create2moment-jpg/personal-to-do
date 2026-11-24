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
| R-015 | Drag and drop of items from anywhere to anywhere | 2026-11-24 | partly done (Today, Week) · rest planned | roadmap N4 |
| R-016 | Keep track of the backlog so feature requests are not lost | 2026-11-24 | done (this file) | — |
| B-001 | Prompt Book: two-page spread view on very wide screens | 2026-11-24 | idea (from R-012) | — |
| B-002 | Prompt Book: streaming AI output and "explain the changes" | 2026-11-24 | idea (from R-013) | — |
| B-003 | Optional emoji on projects and weekly objectives | 2026-11-24 | idea (from R-014) | — |
| B-004 | Drag tasks onto projects, sprint and Upcoming days; notes into the Prompt Book | 2026-11-24 | planned (rest of R-015) | roadmap N4 |

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
