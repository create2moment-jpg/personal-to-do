# ADR-0003: Explicit, versioned, checksummed SQL migrations

- Status: accepted (Phase 1)

## Decision

Plain SQL migration pairs in `migrations/NNNN_name.{up,down}.sql`, applied by
a small runner (`infrastructure/migrations.py`) instead of an ORM
auto-migration tool.

- Each migration runs in one transaction; failure rolls back completely.
- Applied migrations are recorded with a SHA-256 checksum; editing an applied
  migration is detected and refused.
- A database created by a *newer* code version is detected and refused.
- An empty database is initialised automatically. A database holding data is
  never migrated implicitly: `ppos migrate up` takes a verified backup first.
  `PPOS_AUTO_MIGRATE=true` exists for unattended setups but is off by default.
- Downgrades require `--yes` and also take a backup.

## Why

Migrations of a personal, irreplaceable database should be readable,
reviewable and boring. Hand-written SQL makes the exact change visible in code
review; the runner is ~150 lines and fully tested (round trip, rollback on
failure, tamper detection).
