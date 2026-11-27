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
- **Timeboxing** (Today → Timeline): your working hours as a strip with meetings,
  timeboxed tasks and the free time between. Drag a task onto it, click a free
  slot to place one, or set a start time in the task. **Fill my free time**
  proposes start times — top priorities first, never splitting a task, never
  in the past — and saves nothing until you apply. Moving a task to another day
  drops its time; a repeating task keeps it.
- **Task board** (`g a`): every task by state — Backlog, Planned, In progress,
  Blocked, Completed (last 7 / 30 days / all) — with drag and drop, filter and
  project selector.
- **Any duration**: click the time on a card for presets or type `50`,
  `1h20`, `1.5h`; quick add takes `Write spec ~50m`. Tasks without an
  estimate count as a default you choose (Settings → Work & time).
- **Upcoming**: the next seven days with per-day load.
- **Week**: seven-day board with load vs. capacity and meetings per day,
  weekly objectives (with an optional emoji), sprint backlog to drag from, and a guided weekly review.
- **Sprint**: goal, committed and stretch work, burndown, scope changes,
  completion with roll-over and a sprint review.
- **Meetings & time**: import your Outlook calendar (read-only `.ics`), skip a
  recurring meeting with one click, **add your own meetings** (once, or
  daily / weekdays / weekly on chosen days / monthly, any duration), log calls (`call: Priya / ADR review ~30m
  #retrieval`), rate whether meetings were worth it, and see meeting vs. focus
  hours, time per person and per topic. Capacity is computed automatically from
  your working hours (default 08:00–17:00, Europe/Berlin) minus meetings.
- **Tasks**: priority, estimate vs actual, due date, project/area, tags,
  subtasks, dependencies (completion blocked until they're done), and
  **repeats** (every day / weekday / week on chosen days / N weeks / month):
  completing one creates the next. Quick capture: `Water plants every mon`.
- **Backlog** and **Projects & Areas** views (projects can carry an emoji). Deleting a task is undoable:
  it stays in *Recently deleted* (bottom of Backlog) for 30 days.
- **Notes**: a rich-text editor (headings, lists, checklists, tables, code)
  that stores plain Markdown, with autosave and version history (restore is
  non-destructive), kinds incl. journal, meeting, technical, learning,
  career evidence and an **ideas inbox**; links between notes, tasks and projects.
  **Improve** rewrites the selection or the whole note with your local model
  (clearer, shorter, structured, grammar, professional) — you review a diff,
  and accepting keeps the previous text in History.
- **Quick capture** from anywhere (`c`) — plain language works too: press
  **Understand** (⌘/Ctrl+I) and your local AI turns it into the line below,
  which you check before saving. Meetings too:
  `meeting: Sprint planning @mon @10:00 ~1h30 every 2 weeks with Ana, Ben #planning`
  `Review PR #code !2 ~1h30m @tomorrow due:fri +ml-platform` · `idea: …` · `note: …`
- **Command menu** (`Ctrl/⌘+K`) with full-text search, navigation and theme
  switching; `g t` / `g b` / `g n` navigation; `?` shows all shortcuts.
- **Prompt Book** (`g k`): a book for the prompts you give AI assistants —
  chapters and sections nested freely, diary-style pages you flip with ← →,
  `{{variables}}` filled in when you **Copy for Copilot**, every version kept,
  and **Improve with AI** using your *local* model with a side-by-side diff.
  The suggestion streams in as the model writes (Stop any time); **Explain the
  changes** lists what changed, keeping only notes grounded in the two texts.
  The original is never overwritten.
- **Local AI settings** (Settings → Local AI): point the app at any
  OpenAI-compatible server on your machine — llama.cpp (`http://127.0.0.1:8080/v1`),
  vLLM, Ollama, LM Studio. Model is optional (the served model is detected),
  optional API key (kept in memory only, or read from an environment variable),
  reasoning effort, temperature, output and context limits, timeout.
  **Test connection** checks `/models` and a tiny chat; **Apply** takes effect
  immediately, no restart.
- **Knowledge** (`g d`): drop PDFs, Word (.docx), text or Markdown — reviews, level
  frameworks, feedback. Originals stay untouched in your data folder; text is
  indexed per page so every search hit cites its page and section. Optionally
  **extract facts** with your local model: each fact must quote its source
  verbatim or it is dropped, and nothing counts until you accept it.
- **Career** (`g c`): your level framework (L4, L5, …) from accepted
  expectations, with the accepted achievements and strengths you link as
  evidence. Suggestions show the words they share — or, with an embedding model
  set, evidence *similar in meaning* (“coached Ana” for “mentors engineers”);
  you confirm every link.
  Coverage per level is a hypothesis to guide what to collect next, never a
  promotion verdict. Gaps turn into tasks with one click. No AI needed: add
  evidence in your own words (saved as a note in Knowledge, labelled “Your note”).
- **Goals** (`g g`): year → quarter → month goals with progress from linked
  tasks, a number you track or your own estimate, and a pace hint; link them to
  career expectations and skills.
- **Skills** (`g l`): rate yourself 1–5 with history and trend, set targets,
  link evidence from your reviews, turn gaps into goals.
- **Reviews** (`g v`): monthly, bi-monthly, quarterly and annual reviews.
  Numbers come from your own tasks, meetings, sprints, goals, skills, evidence
  and daily/weekly reviews; you write highlights, challenges, learnings and
  next focus — or ask your local AI for a draft whose every bullet must cite
  your records (unsupported bullets are dropped and shown). Finalize to freeze.
- **Insights** (`g i`): 8 / 12 / 26-week trends of tasks done, meetings vs
  focus time, planned work done and estimate accuracy, plus work by project
  and meeting time by topic — all from your own records, with a table view.
- **Assistant** (`g j`): ask about your own notes, documents, tasks and
  prompts — answers cite numbered sources you can open, and uncited answers
  are flagged. Search by meaning when you set an embedding model; **Plan my
  day** proposes three priorities that only apply when you approve.
- **Scales to your monitor**: comfortable text on 24″ and 32″ screens
  (Display size: Auto / S / M / L / XL), optional celebration moments.
- **CLI**: `ppos serve | migrate | backup [--encrypt] | restore | export | demo | doctor | token`.

### Importing your Outlook calendar

Outlook for Windows: *File → Save Calendar → More Options* (pick a date range),
then on **Meetings & time** choose *Import calendar* (or drop the file).
Outlook on the web: *Settings → Calendar → Shared calendars → Publish a
calendar* and download the ICS link. Import is read-only; re-import any time —
your attendance choices and ratings are kept.

## Quick start

Requirements: Python ≥ 3.10, Node ≥ 20.

**One command** (macOS / Linux / WSL):

```bash
bash scripts/install.sh            # add --demo for a sample workspace
.venv/bin/ppos serve --open        # then "Install Personal OS" from Chrome/Edge's address bar
```

It installs the pinned, hash-checked dependencies, builds the web app, sets
your data folder (`~/PersonalProductivityData`, saved in `.env`) and runs
`ppos doctor`. Installed as an app, it opens in its own window; the service
worker caches only the app shell — never your data.

For development:

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

## Security

- The app listens on `127.0.0.1` only. Every API call needs a per-install
  token (created on first start in `LOCAL_DATA_DIR/config/api_token`, mode
  0600); the app's own page receives it as a cookie other sites can't read
  or send. Requests naming another host (DNS rebinding) or changing data from
  another site's origin are refused.
- Scripts: `curl -H "Authorization: Bearer $(ppos token)" http://127.0.0.1:8765/api/tasks`.
- Dev server (`npm run dev`) forwards the token automatically.
- See [docs/threat-model.md](docs/threat-model.md).

## Dependencies

Python packages are pinned with hashes in `requirements.lock` (runtime) and
`requirements-dev.lock` (tests and tooling); Docker and CI install with
`pip install --require-hashes -r requirements.lock && pip install --no-deps -e .`.
Regenerate after changing `pyproject.toml`:
`uv pip compile pyproject.toml --python-version 3.10 --generate-hashes --universal -o requirements.lock`
(add `--extra dev -o requirements-dev.lock` for the dev lock). Web packages are
locked in `apps/web/package-lock.json`.

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
