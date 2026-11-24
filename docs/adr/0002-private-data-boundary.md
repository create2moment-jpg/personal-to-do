# ADR-0002: Physical separation of code and private data

- Status: accepted (Phase 0)

## Decision

All private runtime data lives in `PPOS_LOCAL_DATA_DIR` (default
`~/PersonalProductivityData`), which must be outside the repository. The
application enforces this at startup, and a stdlib-only guard
(`scripts/check_repo_safety.py`) enforces it at commit time (pre-commit hook)
and in CI.

## Why

The repository may later be mirrored to an office repository. Private notes,
performance reviews, embeddings (which leak content) and AI histories must
never be one `git add -A` away from being published.

## Consequences

- Fixtures used by tests and prompt evaluations must be synthetic and live in
  `fixtures/` (allow-listed). Real documents never go there.
- Deliberate exceptions to the guard are listed in
  `config/repo-safety-allowlist.txt` and reviewed like code.
- Mirroring to another repository is a pure code operation (`git push` to a
  second remote); no data migration is involved.
