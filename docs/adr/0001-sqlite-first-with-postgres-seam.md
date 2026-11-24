# ADR-0001: SQLite as the default store, PostgreSQL behind the same ports

- Status: accepted (Phase 1)
- Context: the brief names PostgreSQL (+ pgvector) as the database and SQLite
  as an optional minimal single-user mode.

## Decision

Ship SQLite as the default for Phase 1 and keep PostgreSQL as a second
adapter behind the existing repository / unit-of-work ports, to be added when
a concrete need appears (multi-device access, pgvector, or concurrent writers).

## Why

- The product is single-user and local-first. SQLite in WAL mode gives
  instant reads/writes, zero administration, one file to back up, and a
  consistent online backup API — all things this user benefits from on day one.
- Running a Postgres server just to hold a to-do list raises the setup cost and
  the attack surface, and makes "pull code, keep data" upgrades harder to
  reason about.
- FTS5 provides good full-text search now; it is a *derived* index, so moving
  to Postgres FTS later only means rebuilding it.

## Consequences

- Repository SQL is written portably (no SQLite-only column types in canonical
  tables; timestamps are ISO-8601 text, arrays are JSON).
- Vector search (Phase 6) will sit behind a `VectorStore` port; candidates are
  sqlite-vec for the SQLite profile and pgvector for the Postgres profile.
- A Postgres adapter must pass the same integration test suite
  (`tests/integration`), parameterised by backend.
- Revisit when: >1 device must write concurrently, or vector workloads need
  pgvector features.
