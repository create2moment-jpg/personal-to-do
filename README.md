# Personal Productivity & AI OS

A local-first personal work operating system: plan the day, run the week and
sprint, capture notes and ideas, and — in later phases — use a **local** LLM
over your own private data to write, review and track career evidence.

> **Status:** Phase 1 (tasks, Today, notes, local database) and Phase 1.5
> (premium experience: design system, optimistic UI, keyboard drag and drop,
> rich-text notes, demo workspace) are implemented and tested. Week/Sprint,
> calendar, documents, local AI, goals/skills and reviews follow — see
> [docs/roadmap.md](docs/roadmap.md).

## Show it to someone

```bash
make setup && make build
make demo          # separate workspace with realistic, synthetic data
```

Open http://127.0.0.1:8765. A "Demo data" badge makes it clear nothing is real;
your own workspace is never touched. Try: drag a backlog card onto the board,
press `c` and type `Prep review #demo !1 ~45m @tomorrow`, press `⌘K`, open Notes.

## Principles

- **Your data stays yours.** Everything private lives in `LOCAL_DATA_DIR`
  (default `~/PersonalProductivityData`), outside this repository. The app
  refuses to run otherwise, and a pre-commit/CI guard blocks database files,
  documents and secrets from ever being committed.
- **Deterministic core, AI as assistant.** The app works fully without an LLM.
  When AI arrives it only *proposes*; changes are reviewed and audited
  ([ADR-0004](docs/adr/0004-ai-proposes-application-decides.md)).
- **Safe upgrades.** `git pull` never touches your data. Schema changes are
  explicit (`ppos migrate up`), backed up first and reversible.

## What works today

- **Premium feel**: light theme plus five dark palettes, six accent colours, compact mode,
  optimistic updates with undo, smooth animated drag and drop that also works
  from the keyboard, command menu, live capture preview, responsive to phone width.
- **Today**: greeting, progress ring, daily objective, capacity stat that warns
  when you overcommit, drag/drop board (Planned → In progress → Blocked → Done),
  top-3 priorities, overdue and due-but-unscheduled lists, roll unfinished work to
  tomorrow, end-of-day review, daily journal.
- **Upcoming**: the next seven days with per-day load.
- **Week**: seven-day board with load vs. capacity and meetings per day,
  weekly objectives, sprint backlog to drag from, and a guided weekly review.
- **Sprint**: goal, committed and stretch work, burndown, scope changes,
  completion with roll-over and a sprint review.
- **Meetings & time**: import your Outlook calendar (read-only `.ics`), skip a
  recurring meeting with one click, log calls (`call: Priya / ADR review ~30m
  #retrieval`), rate whether meetings were worth it, and see meeting vs. focus
  hours, time per person and per topic. Capacity is computed automatically from
  your working hours (default 08:00–17:00, Europe/Berlin) minus meetings.
- **Tasks**: priority, estimate vs actual, due date, project/area, tags,
  subtasks, dependencies (completion blocked until they're done), recurrence
  rule stored.
- **Backlog** and **Projects & Areas** views.
- **Notes**: a rich-text editor (headings, lists, checklists, tables, code)
  that stores plain Markdown, with autosave and version history (restore is
  non-destructive), kinds incl. journal, meeting, technical, learning,
  career evidence and an **ideas inbox**; links between notes, tasks and projects.
- **Quick capture** from anywhere (`c`):
  `Review PR #code !2 ~1h30m @tomorrow due:fri +ml-platform` · `idea: …` · `note: …`
- **Command menu** (`Ctrl/⌘+K`) with full-text search, navigation and theme
  switching; `g t` / `g b` / `g n` navigation; `?` shows all shortcuts.
- **CLI**: `ppos serve | migrate | backup | restore | export | demo | doctor`.

### Importing your Outlook calendar

Outlook for Windows: *File → Save Calendar → More Options* (pick a date range),
then on **Meetings & time** choose *Import calendar* (or drop the file).
Outlook on the web: *Settings → Calendar → Shared calendars → Publish a
calendar* and download the ICS link. Import is read-only; re-import any time —
your attendance choices and ratings are kept.

## Quick start

Requirements: Python ≥ 3.10, Node ≥ 20.

```bash
make setup          # venv + Python/Node deps + git hooks (commit author: Jimmy)
make build          # build the web UI
make api            # http://127.0.0.1:8765
```

Development with hot reload: `make api` in one terminal, `make web` in another
(http://127.0.0.1:5173, proxies `/api`).

Configuration is via environment variables or a git-ignored `.env`; see
[.env.example](.env.example). The most important one:

```bash
export PPOS_LOCAL_DATA_DIR=~/PersonalProductivityData
```

Docker (loopback-only, data bind-mounted from the host):

```bash
PPOS_LOCAL_DATA_DIR=~/PersonalProductivityData docker compose -f deploy/docker-compose.yml up -d --build
```

## Backups

```bash
ppos backup                     # verified archive in LOCAL_DATA_DIR/backups
ppos restore <archive> --force  # current data is moved aside, never deleted
ppos export                     # everything as portable JSON
```

Details: [docs/data-and-backups.md](docs/data-and-backups.md).

## Development

```bash
make check      # ruff, mypy --strict, pytest, tsc, vitest, repo safety guard
make e2e        # Playwright end-to-end tests against a throwaway demo workspace
```

UI stack: React 18 + TypeScript + Vite, TanStack Query, dnd-kit, cmdk, TipTap,
Framer Motion, Lucide, Sonner. Design rules: [docs/design-system.md](docs/design-system.md).

| Path | Contents |
|---|---|
| `apps/api` | FastAPI presentation layer |
| `apps/web` | React + TypeScript UI |
| `packages/ppos/domain` | entities and rules (no I/O) |
| `packages/ppos/application` | use cases and ports |
| `packages/ppos/infrastructure` | SQLite, FTS5, migrations, backup, config |
| `packages/ppos/ai`, `analytics` | reserved for Phases 5 and 8 |
| `migrations/` | versioned `up`/`down` SQL |
| `prompts/`, `schemas/` | AI prompt library contract (Phase 5+) |
| `scripts/` | repo safety guard, git hook installer |
| `docs/` | architecture, ADRs, threat model, roadmap |

Commit rules: small logical commits, imperative messages, author `Jimmy`
(`scripts/install-git-hooks.sh` sets the name; supply your own email via
`PPOS_GIT_AUTHOR_EMAIL`). Never commit anything from `LOCAL_DATA_DIR`.

## Documentation

- [Backlog — every feature request and its status](docs/backlog.md)

- [Architecture](docs/architecture.md)
- [Design system](docs/design-system.md)
- [Decisions (ADRs)](docs/adr/)
- [Threat model](docs/threat-model.md)
- [Data, backups and upgrades](docs/data-and-backups.md)
- [Roadmap, open questions, technical debt](docs/roadmap.md)
