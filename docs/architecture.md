# Architecture

Status: Phase 0 + Phase 1 implemented. This document describes what exists and
the seams later phases plug into. Decisions are recorded in [`adr/`](adr/).

## 1. Shape of the system

```
 Browser (apps/web, React + TS)
        │  JSON over HTTP, same origin
        ▼
 apps/api/ppos_api      ── presentation: FastAPI routes, request/response models, error mapping
        │
 packages/ppos/application ── use cases (TaskService, NoteService, DayService, CaptureService…)
        │        depends only on ports (Protocols) in application/ports.py
        ▼
 packages/ppos/domain   ── entities + rules, no I/O (Task, Note, DailyPlan, capacity, capture grammar)

 packages/ppos/infrastructure ── implements ports: SQLite repos, FTS5, migrations, backup, config
 packages/ppos/ai              ── Phase 5+: providers, prompts, context compiler, validation, workflows
 packages/ppos/analytics       ── Phase 8: read-only projections over canonical tables + audit log
 packages/ppos/bootstrap.py    ── composition root (the only place that knows concrete classes)
```

Dependency rule: arrows point inward. `domain` imports nothing from the project
except `shared`; `application` never imports `infrastructure`; only
`bootstrap.py` and the CLI wire concrete adapters. One deployable process (no
microservices); background work will run in an in-process worker first
(Phase 4), behind a job-queue port so it can move out later.

## 2. Code vs. private data

| Lives in Git (this repo) | Lives in `LOCAL_DATA_DIR` (default `~/PersonalProductivityData`) |
|---|---|
| source, tests, migrations, prompt templates, schemas, safe fixtures, docs, deploy config | `db/ppos.sqlite3`, `notes/`, `documents/` (originals), `indexes/`, `cache/`, `ai/` (histories, model state), `backups/`, `exports/`, `config/` (private settings) |

Enforced, not just documented:

- The app refuses to start if `LOCAL_DATA_DIR` is inside the repository or vice
  versa (`infrastructure/config.py::enforce_data_boundary`).
- Data directories are created `0700`; backups and exports `0600`.
- `scripts/check_repo_safety.py` runs as a pre-commit hook and in CI; it
  rejects database files, document/binary formats, oversized files, `.env`
  files, private keys and common token patterns.
- `.gitignore` covers the same classes of files as a second line of defence.

Pulling a new version of the code never touches private data: a database with
pending migrations makes startup fail with instructions (`ppos migrate up`,
which takes a verified backup first). Only an empty, brand-new database is
initialised automatically.

## 3. Storage tiers

| Tier | Phase 1 implementation | Rule |
|---|---|---|
| Canonical relational store | SQLite (WAL, foreign keys, CHECK constraints) | Source of truth for all state. |
| Version history | `note_versions` (one immutable row per editing window) | Append-only; restore creates a new version. |
| Audit trail | `audit_log` with `actor ∈ {user, system, ai}` | Append-only (DB trigger blocks UPDATE). |
| Full-text index | FTS5 `search_index`, maintained by triggers | Derived; rebuildable; points to `(entity_type, entity_id)`. |
| Original documents | `LOCAL_DATA_DIR/documents` (Phase 4) | Content-hashed, never modified. |
| Vector index | Phase 6, behind a `VectorStore` port (sqlite-vec or pgvector) | Derived; every embedding references chunk → document → hash. |
| Extracted facts | Phase 4/7 table with provenance columns | Every fact: doc id, page/section/chunk, extractor + model + prompt version, timestamp, confidence. |
| Analytics | Phase 8 materialised views / tables | Derived from canonical + audit. |

SQLite is the default (see ADR-0001). The repository/UoW ports are the seam for
a PostgreSQL adapter when multi-device or pgvector is needed; the SQL is kept
portable (ISO-8601 text timestamps, JSON arrays, no SQLite-only types in the
canonical tables apart from FTS5, which is a derived index).

## 4. Key domain rules (Phase 1)

- Task states: `backlog → planned → in_progress → blocked → done` (any
  transition allowed; invariants applied in one place, `Task.transition` /
  `TaskService.move`). Moving to backlog unschedules; scheduling promotes
  backlog to planned; leaving `done` clears `completed_at`.
- Completion is refused while a dependency is unfinished; dependency and
  subtask cycles are rejected.
- Capacity = Σ remaining estimates of open top-level tasks for the day;
  unestimated tasks count as 30 min so leaving estimates blank cannot hide
  overcommitment. Subtasks are covered by their parent's estimate.
- At most three top priorities per day.
- Quick capture grammar is deterministic and offline (`domain/capture.py`);
  the LLM capture in Phase 5 *proposes* the same structure for review.

## 5. AI layer contract (Phase 5+, designed now)

1. **The model proposes; the application decides.** AI output is parsed into
   typed proposals (pydantic models generated from `schemas/`), validated,
   shown as a diff, and applied through the same application services with
   `actor="ai"` in the audit log. Writes need approval unless a capability is
   explicitly configured as safe automation.
2. **Provider abstraction**: `LLMProvider` port with Ollama and vLLM (OpenAI
   compatible) adapters; model id, context size, temperature, max tokens,
   concurrency, timeout and retry policy come from config, not code. No cloud
   fallback unless explicitly enabled.
3. **Capability registry**: each capability (summarize, extract, classify,
   rewrite, plan, review, …) binds a versioned prompt from `prompts/`, an input
   schema, an output schema, a context budget and a small-model variant.
4. **Context compiler** (Phase 6): never "send the database". Layers, in order
   of priority, each with a token budget: task-specific structured facts
   (deterministic SQL) → pinned items (today's plan, active sprint, goals) →
   FTS hits → vector hits → summaries of older periods. Every item carries its
   source id so the answer can cite it.
5. **Epistemic labelling**: outputs separate `fact` (canonical record),
   `document_claim` (with provenance), `user_statement`, `inference`, and
   `recommendation`. The UI renders these differently.
6. **Reproducibility**: important outputs store model id, prompt id + version,
   input hash and parameters.

## 6. Error handling and observability

- Expected errors are typed (`shared/errors.py`) and mapped to HTTP codes in
  one place; unexpected errors are 500s with logs.
- Each request gets a `Server-Timing` header; API logs contain method, path,
  status and latency, never request bodies (private content).
- `ppos doctor` checks boundary, schema version and `PRAGMA integrity_check`.

## 7. Performance notes

- One short-lived SQLite connection per unit of work; WAL allows concurrent
  readers with one writer, which matches single-user usage.
- Indexes cover the hot paths: tasks by `(scheduled_date, status, position)`,
  by status, project, parent and completion time; notes by kind/date.
- List endpoints are paginated (`limit`/`offset`); history is loaded on demand.
- Nothing expensive runs in a request today; Phase 4 introduces the job queue
  before any extraction/embedding work exists.
