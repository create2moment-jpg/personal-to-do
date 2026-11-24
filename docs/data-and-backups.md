# Private data, backups and upgrades

## Where data lives

`PPOS_LOCAL_DATA_DIR` (default `~/PersonalProductivityData`):

```
PersonalProductivityData/
├── db/ppos.sqlite3      canonical database (+ -wal/-shm while running)
├── notes/               (Phase 4+) human-readable note mirror
├── documents/           original documents, content-hashed (ab/abcdef….pdf), 0600
├── indexes/  cache/     derived, rebuildable
├── ai/                  (Phase 5) AI job history, model state
├── config/              private configuration
├── backups/             verified backup archives
└── exports/             JSON exports
```

The app refuses to run if this directory is inside the repository (or the
repository is inside it).

## Backup

```bash
ppos backup                          # -> LOCAL_DATA_DIR/backups/ppos-<ts>-manual.tar.gz
ppos backup --dest /mnt/usb/ppos     # somewhere else (recommended: off-machine too)
```

The archive holds a consistent SQLite snapshot (online backup API — safe while
the app runs), every file except `cache/`, `backups/`, `exports/`, and a
`manifest.json` with SHA-256 checksums, app version and schema version.
Archives are `0600`. Encrypt them before copying to cloud storage
(`age`/`gpg`); built-in encryption is Phase 9.

## Restore

```bash
ppos restore path/to/backup.tar.gz            # into an empty data dir
ppos restore path/to/backup.tar.gz --force    # replace existing data
```

Restore verifies every checksum in a staging directory first. With `--force`,
the current data dir is **moved aside** to
`<data_dir>.pre-restore-<timestamp>` (never deleted); existing backups are
carried over. If the backup is from an older schema, run `ppos migrate up`
afterwards.

## Export

`ppos export` writes every canonical table to a single JSON file — readable
without this app.

## Upgrading the code

```bash
git pull
pip install -e ".[dev]" && (cd apps/web && npm ci && npm run build)
ppos migrate status
ppos migrate up        # takes a backup automatically, then migrates
```

If you skip `migrate up`, the app refuses to start rather than migrating
silently. `ppos doctor` checks the boundary, schema version and database
integrity.

## Moving to another machine / mirroring the code

Code: push to any remote, e.g. an office mirror (`git remote add office …`).
No data is involved. Data: `ppos backup`, copy the archive, `ppos restore` on
the new machine.
