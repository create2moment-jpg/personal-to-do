# Personal Productivity & AI OS

A local-first personal work operating system: plan the day, run the week and
sprint, capture notes and ideas, and — in later phases — use a **local** LLM
over your own private data to write, review and track career evidence.

> **Status:** Phase 1 (tasks, Today, notes, local database) is implemented and
> tested. Week/Sprint, calendar, documents, local AI, goals/skills and reviews
> follow — see [docs/roadmap.md](docs/roadmap.md).

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

- **Today**: daily objective, capacity meter that warns when you overcommit,
  drag/drop board (Planned → In progress → Blocked/Waiting → Done), top-3
  priorities, overdue and due-but-unscheduled lists, roll unfinished work to
  tomorrow, end-of-day review, daily journal.
- **Tasks**: priority, estimate vs actual, due date, project/area, tags,
  subtasks, dependencies (completion blocked until they're done), recurrence
  rule stored.
- **Backlog** and **Projects & Areas** views.
- **Notes**: Markdown notes with autosave and version history (restore is
  non-destructive), kinds incl. journal, meeting, technical, learning,
  career evidence and an **ideas inbox**; links between notes, tasks and projects.
- **Quick capture** from anywhere (`c`):
  `Review PR #code !2 ~1h30m @tomorrow due:fri +ml-platform` · `idea: …` · `note: …`
- **Command palette** (`Ctrl/⌘+K`) with full-text search across tasks and notes.
- **CLI**: `ppos serve | migrate | backup | restore | export | doctor`.

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
```

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

- [Architecture](docs/architecture.md)
- [Decisions (ADRs)](docs/adr/)
- [Threat model](docs/threat-model.md)
- [Data, backups and upgrades](docs/data-and-backups.md)
- [Roadmap, open questions, technical debt](docs/roadmap.md)
