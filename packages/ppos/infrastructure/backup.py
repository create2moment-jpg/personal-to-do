"""Backup, restore and export for LOCAL_DATA_DIR.

A backup is a ``.tar.gz`` containing a consistent SQLite snapshot (via the
online backup API, safe while the app runs), every other private file except
caches/backups/exports, and a ``manifest.json`` with SHA-256 checksums that
restore verifies before touching anything.
"""

from __future__ import annotations

import hashlib
import io
import json
import shutil
import sqlite3
import tarfile
import tempfile
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path, PurePosixPath
from typing import Any

from ppos import __version__
from ppos.infrastructure.config import Settings, ensure_data_dir
from ppos.infrastructure.db import connect
from ppos.infrastructure.migrations import current_version
from ppos.shared.errors import PposError

EXCLUDED_TOP_LEVEL = {"backups", "cache", "exports"}
MANIFEST = "manifest.json"
DB_REL = "db/ppos.sqlite3"


class BackupError(PposError):
    pass


@dataclass(frozen=True)
class BackupInfo:
    path: Path
    files: int
    schema_version: int
    created_at: str


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as fh:
        for chunk in iter(lambda: fh.read(1 << 20), b""):
            digest.update(chunk)
    return digest.hexdigest()


def create_backup(
    settings: Settings, label: str = "manual", dest_dir: Path | None = None
) -> BackupInfo:
    root = ensure_data_dir(settings)
    dest_dir = dest_dir or settings.backups_dir
    dest_dir.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S%fZ")
    safe_label = "".join(c for c in label if c.isalnum() or c in "-_")[:40] or "backup"
    out = dest_dir / f"ppos-{stamp}-{safe_label}.tar.gz"

    with tempfile.TemporaryDirectory(prefix="ppos-backup-") as tmp:
        staging = Path(tmp)
        files: dict[str, str] = {}
        schema_version = 0
        if settings.db_path.exists():
            snap = staging / "ppos.sqlite3"
            src = connect(settings.db_path)
            dst = sqlite3.connect(snap)
            try:
                src.backup(dst)
                schema_version = current_version(dst)
            finally:
                dst.close()
                src.close()
            files[DB_REL] = _sha256(snap)

        others: list[tuple[str, Path]] = []
        for path in sorted(root.rglob("*")):
            rel = path.relative_to(root)
            if not path.is_file() or path.is_symlink():
                continue
            if rel.parts[0] in EXCLUDED_TOP_LEVEL or rel.parts[0] == "db":
                continue
            others.append((rel.as_posix(), path))
            files[rel.as_posix()] = _sha256(path)

        manifest: dict[str, Any] = {
            "format": 1,
            "app_version": __version__,
            "schema_version": schema_version,
            "created_at": datetime.now(timezone.utc).isoformat(),
            "label": label,
            "files": files,
        }
        with tarfile.open(out, "w:gz") as tar:
            data = json.dumps(manifest, indent=2).encode()
            info = tarfile.TarInfo(MANIFEST)
            info.size = len(data)
            tar.addfile(info, io.BytesIO(data))
            if DB_REL in files:
                tar.add(staging / "ppos.sqlite3", arcname=DB_REL)
            for rel_name, path in others:
                tar.add(path, arcname=rel_name)
    out.chmod(0o600)
    return BackupInfo(out, len(files), schema_version, manifest["created_at"])


def _safe_members(tar: tarfile.TarFile) -> list[tarfile.TarInfo]:
    members = []
    for m in tar.getmembers():
        p = PurePosixPath(m.name)
        if p.is_absolute() or ".." in p.parts or not (m.isfile() or m.isdir()):
            raise BackupError(f"unsafe archive member: {m.name}")
        members.append(m)
    return members


def read_manifest(archive: Path) -> dict[str, Any]:
    with tarfile.open(archive, "r:gz") as tar:
        fh = tar.extractfile(MANIFEST)
        if fh is None:
            raise BackupError("backup has no manifest")
        manifest: dict[str, Any] = json.loads(fh.read())
        return manifest


def restore_backup(settings: Settings, archive: Path, *, force: bool = False) -> Path | None:
    """Restore ``archive`` into LOCAL_DATA_DIR.

    Verifies every checksum in a staging directory first. If the data dir
    already holds a database, ``force`` is required and the current contents
    are moved aside (never deleted) to ``<data_dir>.pre-restore-<stamp>``,
    whose path is returned.
    """
    root = settings.local_data_dir
    with tempfile.TemporaryDirectory(prefix="ppos-restore-") as tmp:
        staging = Path(tmp) / "data"
        staging.mkdir()
        with tarfile.open(archive, "r:gz") as tar:
            members = _safe_members(tar)
            if hasattr(tarfile, "data_filter"):  # defence in depth on patched Pythons
                tar.extractall(staging, members=members, filter="data")
            else:
                tar.extractall(staging, members=members)  # noqa: S202 - members validated above
        manifest = json.loads((staging / MANIFEST).read_text(encoding="utf-8"))
        if manifest.get("format") != 1:
            raise BackupError(f"unsupported backup format {manifest.get('format')}")
        for rel, expected in manifest["files"].items():
            target = staging / rel
            if not target.is_file() or _sha256(target) != expected:
                raise BackupError(f"checksum mismatch for {rel}; backup is corrupt")
        (staging / MANIFEST).unlink()

        moved_aside: Path | None = None
        if settings.db_path.exists():
            if not force:
                raise BackupError(
                    f"{root} already contains a database; re-run with --force to replace it "
                    "(current data will be moved aside, not deleted)"
                )
            stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
            moved_aside = root.with_name(f"{root.name}.pre-restore-{stamp}")
            shutil.move(str(root), moved_aside)
            # Keep historical backups with the live data dir.
            if (moved_aside / "backups").exists():
                (root).mkdir(parents=True)
                shutil.move(str(moved_aside / "backups"), root / "backups")
        root.mkdir(parents=True, exist_ok=True)
        for item in staging.iterdir():
            dest = root / item.name
            if dest.exists():
                if dest.is_dir():
                    shutil.copytree(item, dest, dirs_exist_ok=True)
                else:
                    shutil.copy2(item, dest)
            else:
                shutil.move(str(item), dest)
    for stale in ("ppos.sqlite3-wal", "ppos.sqlite3-shm"):
        (root / "db" / stale).unlink(missing_ok=True)
    ensure_data_dir(settings)
    return moved_aside


EXPORT_TABLES = (
    "projects", "tasks", "task_dependencies", "notes", "note_versions", "links",
    "daily_plans", "audit_log", "schema_migrations",
)  # fmt: skip


def export_json(settings: Settings, dest: Path | None = None) -> Path:
    """Portable, human-readable export of all canonical tables."""
    root = ensure_data_dir(settings)
    dest = dest or root / "exports" / (
        f"ppos-export-{datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ')}.json"
    )
    conn = connect(settings.db_path)
    try:
        payload: dict[str, Any] = {
            "format": 1,
            "app_version": __version__,
            "exported_at": datetime.now(timezone.utc).isoformat(),
            "tables": {},
        }
        for table in EXPORT_TABLES:
            rows = conn.execute(f"SELECT * FROM {table}").fetchall()
            payload["tables"][table] = [dict(r) for r in rows]
    finally:
        conn.close()
    dest.parent.mkdir(parents=True, exist_ok=True)
    dest.write_text(json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8")
    dest.chmod(0o600)
    return dest
