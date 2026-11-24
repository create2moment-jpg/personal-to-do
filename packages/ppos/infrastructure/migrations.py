"""Explicit, versioned, reversible SQL migrations.

Files live in ``migrations/`` as ``NNNN_name.up.sql`` / ``NNNN_name.down.sql``.
Applied migrations are recorded with a checksum; editing an applied migration
is detected and refused. The application never migrates a database holding
data implicitly: ``ppos migrate up`` takes a backup first.
"""

from __future__ import annotations

import hashlib
import re
import sqlite3
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path

from ppos.shared.errors import MigrationRequiredError, PposError

_FILE_RE = re.compile(r"^(\d{4})_([a-z0-9_]+)\.up\.sql$")


@dataclass(frozen=True)
class Migration:
    version: int
    name: str
    up_sql: str
    down_sql: str | None

    @property
    def checksum(self) -> str:
        return hashlib.sha256(self.up_sql.encode()).hexdigest()


class MigrationError(PposError):
    pass


def discover(migrations_dir: Path) -> list[Migration]:
    found: list[Migration] = []
    for path in sorted(migrations_dir.glob("*.up.sql")):
        m = _FILE_RE.match(path.name)
        if not m:
            raise MigrationError(f"badly named migration file: {path.name}")
        down = path.with_name(path.name.replace(".up.sql", ".down.sql"))
        found.append(
            Migration(
                version=int(m.group(1)),
                name=m.group(2),
                up_sql=path.read_text(encoding="utf-8"),
                down_sql=down.read_text(encoding="utf-8") if down.exists() else None,
            )
        )
    versions = [m.version for m in found]
    if versions != list(range(1, len(found) + 1)):
        raise MigrationError(f"migration versions must be contiguous from 1: {versions}")
    return found


def _ensure_table(conn: sqlite3.Connection) -> None:
    conn.execute(
        """CREATE TABLE IF NOT EXISTS schema_migrations (
            version INTEGER PRIMARY KEY,
            name TEXT NOT NULL,
            checksum TEXT NOT NULL,
            applied_at TEXT NOT NULL
        )"""
    )


def applied(conn: sqlite3.Connection) -> dict[int, str]:
    _ensure_table(conn)
    return {
        row[0]: row[1] for row in conn.execute("SELECT version, checksum FROM schema_migrations")
    }


def current_version(conn: sqlite3.Connection) -> int:
    done = applied(conn)
    return max(done, default=0)


def pending(conn: sqlite3.Connection, migrations: list[Migration]) -> list[Migration]:
    done = applied(conn)
    for mig in migrations:
        if mig.version in done and done[mig.version] != mig.checksum:
            raise MigrationError(
                f"migration {mig.version:04d}_{mig.name} was modified after being applied; "
                "create a new migration instead"
            )
    unknown = set(done) - {m.version for m in migrations}
    if unknown:
        raise MigrationError(
            f"database has migrations {sorted(unknown)} unknown to this code version "
            "(was it created by a newer release?)"
        )
    return [m for m in migrations if m.version not in done]


def _run_script(conn: sqlite3.Connection, sql: str) -> None:
    # executescript() would COMMIT implicitly; run statements inside our own
    # transaction instead so each migration is atomic.
    for statement in _split_sql(sql):
        conn.execute(statement)


def _split_sql(sql: str) -> list[str]:
    statements: list[str] = []
    buffer = ""
    for line in sql.splitlines(keepends=True):
        if line.strip().startswith("--") and not buffer.strip():
            continue
        buffer += line
        if sqlite3.complete_statement(buffer):
            if buffer.strip():
                statements.append(buffer.strip())
            buffer = ""
    if buffer.strip():
        raise MigrationError(f"incomplete SQL statement: {buffer.strip()[:80]}")
    return statements


def upgrade(
    conn: sqlite3.Connection, migrations: list[Migration], target: int | None = None
) -> list[int]:
    ran: list[int] = []
    for mig in pending(conn, migrations):
        if target is not None and mig.version > target:
            break
        conn.execute("BEGIN IMMEDIATE")
        try:
            _run_script(conn, mig.up_sql)
            conn.execute(
                "INSERT INTO schema_migrations (version, name, checksum, applied_at)"
                " VALUES (?,?,?,?)",
                (mig.version, mig.name, mig.checksum, datetime.now(timezone.utc).isoformat()),
            )
            conn.execute("COMMIT")
        except Exception:
            conn.execute("ROLLBACK")
            raise
        ran.append(mig.version)
    return ran


def downgrade(conn: sqlite3.Connection, migrations: list[Migration], steps: int = 1) -> list[int]:
    by_version = {m.version: m for m in migrations}
    reverted: list[int] = []
    for version in sorted(applied(conn), reverse=True)[:steps]:
        mig = by_version.get(version)
        if mig is None or mig.down_sql is None:
            raise MigrationError(f"migration {version:04d} is not reversible")
        conn.execute("BEGIN IMMEDIATE")
        try:
            _run_script(conn, mig.down_sql)
            conn.execute("DELETE FROM schema_migrations WHERE version = ?", (version,))
            conn.execute("COMMIT")
        except Exception:
            conn.execute("ROLLBACK")
            raise
        reverted.append(version)
    return reverted


def is_empty_database(conn: sqlite3.Connection) -> bool:
    row = conn.execute(
        "SELECT count(*) FROM sqlite_master WHERE type = 'table' AND name <> 'schema_migrations'"
        " AND name NOT LIKE 'sqlite_%'"
    ).fetchone()
    return int(row[0]) == 0


def prepare_database(
    conn: sqlite3.Connection, migrations_dir: Path, auto_migrate: bool
) -> list[int]:
    """Startup check. A brand-new database is initialised automatically (no
    data at risk); an existing one with pending migrations is only upgraded
    when ``auto_migrate`` is set, otherwise startup fails with instructions."""
    migrations = discover(migrations_dir)
    todo = pending(conn, migrations)
    if not todo:
        return []
    if is_empty_database(conn) or auto_migrate:
        return upgrade(conn, migrations)
    raise MigrationRequiredError(
        f"{len(todo)} pending migration(s) "
        f"({', '.join(f'{m.version:04d}_{m.name}' for m in todo)}). "
        "Run `ppos migrate up` (it backs up your data first)."
    )
