"""`ppos` command-line interface: serve, migrate, backup, restore, export, doctor."""

from __future__ import annotations

import argparse
import getpass
import logging
import os
import sys
from pathlib import Path

from ppos import __version__
from ppos.infrastructure import migrations as mig
from ppos.infrastructure.api_token import load_or_create_token, token_path
from ppos.infrastructure.backup import create_backup, export_json, read_manifest, restore_backup
from ppos.infrastructure.backup_crypto import is_encrypted
from ppos.infrastructure.config import REPO_ROOT, Settings, enforce_data_boundary, ensure_data_dir
from ppos.infrastructure.db import connect
from ppos.shared.errors import PposError


def _settings(args: argparse.Namespace) -> Settings:
    if getattr(args, "data_dir", None):
        return Settings(local_data_dir=Path(args.data_dir))
    return Settings()


def cmd_serve(args: argparse.Namespace) -> int:
    import uvicorn

    from ppos_api.main import create_app

    settings = _settings(args)
    app = create_app(settings)
    host, port = args.host or settings.host, args.port or settings.port
    if args.open:
        import threading
        import webbrowser

        shown = "127.0.0.1" if host in ("0.0.0.0", "::") else host  # noqa: S104
        threading.Timer(1.5, webbrowser.open, args=(f"http://{shown}:{port}/",)).start()
    uvicorn.run(app, host=host, port=port, log_level=settings.log_level.lower())
    return 0


def cmd_migrate(args: argparse.Namespace) -> int:
    settings = _settings(args)
    ensure_data_dir(settings)
    migrations = mig.discover(settings.migrations_dir)
    conn = connect(settings.db_path)
    try:
        todo = mig.pending(conn, migrations)
        current = mig.current_version(conn)
        if args.action == "status":
            print(f"database: {settings.db_path}")
            print(f"current schema version: {current}")
            for m in migrations:
                state = "pending" if m in todo else "applied"
                print(f"  {m.version:04d}_{m.name}: {state}")
            return 0
        needs_change = bool(todo) if args.action == "up" else current > 0
        if needs_change and not mig.is_empty_database(conn) and not args.no_backup:
            info = create_backup(settings, label=f"pre-migrate-{args.action}")
            print(f"backup written: {info.path}")
        if args.action == "up":
            ran = mig.upgrade(conn, migrations, target=args.target)
            print(f"applied: {ran or 'nothing to do'}")
        else:
            if not args.yes:
                print("refusing to downgrade without --yes (downgrades can drop data)")
                return 2
            ran = mig.downgrade(conn, migrations, steps=args.steps)
            print(f"reverted: {ran or 'nothing to do'}")
    finally:
        conn.close()
    return 0


def _passphrase(confirm: bool) -> str:
    """PPOS_BACKUP_PASSPHRASE, else ask (twice when creating)."""
    env = os.environ.get("PPOS_BACKUP_PASSPHRASE")
    if env:
        return env
    first = getpass.getpass("Backup passphrase: ")
    if confirm and getpass.getpass("Repeat passphrase: ") != first:
        raise SystemExit("passphrases do not match")
    return first


def cmd_backup(args: argparse.Namespace) -> int:
    passphrase = _passphrase(confirm=True) if args.encrypt else None
    info = create_backup(_settings(args), label=args.label,
                         dest_dir=Path(args.dest) if args.dest else None,
                         passphrase=passphrase)  # fmt: skip
    print(f"backup written: {info.path} ({info.files} files, schema v{info.schema_version})")
    return 0


def cmd_restore(args: argparse.Namespace) -> int:
    settings = _settings(args)
    enforce_data_boundary(settings)
    archive = Path(args.archive)
    passphrase = _passphrase(confirm=False) if is_encrypted(archive) else None
    manifest = read_manifest(archive, passphrase)
    print(f"restoring backup from {manifest['created_at']} (schema v{manifest['schema_version']})")
    aside = restore_backup(settings, archive, force=args.force, passphrase=passphrase)
    if aside:
        print(f"previous data moved to {aside}")
    print(f"restored into {settings.local_data_dir}")
    return 0


def cmd_export(args: argparse.Namespace) -> int:
    path = export_json(_settings(args), Path(args.dest) if args.dest else None)
    print(f"export written: {path}")
    return 0


def cmd_demo(args: argparse.Namespace) -> int:
    from ppos.bootstrap import build_container
    from ppos.demo import seed_demo

    settings = _settings(args)
    if not getattr(args, "data_dir", None) and "PPOS_LOCAL_DATA_DIR" not in os.environ:
        settings = Settings(local_data_dir=Path.home() / "PersonalProductivityDemo")
    counts = seed_demo(build_container(settings))
    print(f"demo workspace ready in {settings.local_data_dir}: {counts}")
    print(f"run it with: ppos --data-dir {settings.local_data_dir} serve")
    return 0


def cmd_doctor(args: argparse.Namespace) -> int:
    settings = _settings(args)
    print(f"ppos {__version__}")
    print(f"repository:     {REPO_ROOT}")
    print(f"LOCAL_DATA_DIR: {settings.local_data_dir}")
    enforce_data_boundary(settings)
    print("data boundary:  OK (data dir is outside the repository)")
    if settings.db_path.exists():
        conn = connect(settings.db_path)
        try:
            todo = mig.pending(conn, mig.discover(settings.migrations_dir))
            print(f"schema:         v{mig.current_version(conn)}, {len(todo)} pending")
            ok = conn.execute("PRAGMA integrity_check").fetchone()[0]
            print(f"integrity:      {ok}")
        finally:
            conn.close()
    else:
        print("database:       not created yet (run `ppos serve` or `ppos migrate up`)")
    if not settings.auth:
        print("API access:     UNPROTECTED (PPOS_AUTH=false) — use only for debugging")
    elif settings.api_token:
        print("API access:     token from PPOS_API_TOKEN")
    else:
        path = token_path(settings)
        mode = oct(path.stat().st_mode & 0o777) if path.exists() else "not created yet"
        print(f"API access:     token file {path} ({mode})")
    return 0


def cmd_token(args: argparse.Namespace) -> int:
    """Print the API token for scripts: curl -H "Authorization: Bearer $(ppos token)" …"""
    settings = _settings(args)
    enforce_data_boundary(settings)
    print(load_or_create_token(settings))
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="ppos", description=__doc__)
    parser.add_argument("--version", action="version", version=__version__)
    parser.add_argument("--data-dir", help="override PPOS_LOCAL_DATA_DIR")
    sub = parser.add_subparsers(dest="command", required=True)

    p = sub.add_parser("serve", help="run the API (and built web UI)")
    p.add_argument("--host")
    p.add_argument("--port", type=int)
    p.add_argument("--open", action="store_true", help="open the app in your browser")
    p.set_defaults(func=cmd_serve)

    p = sub.add_parser("migrate", help="inspect or apply schema migrations")
    p.add_argument("action", choices=["status", "up", "down"])
    p.add_argument("--target", type=int, help="up: stop at this version")
    p.add_argument("--steps", type=int, default=1, help="down: number of migrations")
    p.add_argument("--yes", action="store_true", help="down: confirm")
    p.add_argument("--no-backup", action="store_true", help="skip the automatic backup")
    p.set_defaults(func=cmd_migrate)

    p = sub.add_parser("backup", help="write a verified backup archive")
    p.add_argument("--label", default="manual")
    p.add_argument("--dest", help="directory (default: LOCAL_DATA_DIR/backups)")
    p.add_argument(
        "--encrypt",
        action="store_true",
        help="encrypt with a passphrase (asked, or PPOS_BACKUP_PASSPHRASE) — needed to restore",
    )
    p.set_defaults(func=cmd_backup)

    p = sub.add_parser("restore", help="restore a backup archive")
    p.add_argument("archive")
    p.add_argument("--force", action="store_true", help="replace existing data (moved aside)")
    p.set_defaults(func=cmd_restore)

    p = sub.add_parser("export", help="export all data as JSON")
    p.add_argument("--dest")
    p.set_defaults(func=cmd_export)

    p = sub.add_parser("demo", help="create a synthetic showcase workspace (separate data dir)")
    p.set_defaults(func=cmd_demo)

    p = sub.add_parser("doctor", help="check configuration, data boundary and DB integrity")
    p.set_defaults(func=cmd_doctor)

    p = sub.add_parser("token", help="print the local API token (for scripts)")
    p.set_defaults(func=cmd_token)
    return parser


def main(argv: list[str] | None = None) -> int:
    for stream in (sys.stdout, sys.stderr):  # Windows consoles may be cp1252: never crash on "—"
        if hasattr(stream, "reconfigure"):
            stream.reconfigure(errors="replace")
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s %(message)s")
    args = build_parser().parse_args(argv)
    try:
        return int(args.func(args))
    except PposError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
