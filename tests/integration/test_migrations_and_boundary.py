import sqlite3
from pathlib import Path

import pytest

from ppos.infrastructure import migrations as mig
from ppos.infrastructure.config import DEFAULT_MIGRATIONS_DIR, REPO_ROOT, Settings, ensure_data_dir
from ppos.infrastructure.db import connect
from ppos.shared.errors import DataBoundaryError, MigrationRequiredError
from tests.conftest import POSIX_MODES


def test_up_down_up_roundtrip(tmp_path: Path) -> None:
    conn = connect(tmp_path / "x.db")
    migrations = mig.discover(DEFAULT_MIGRATIONS_DIR)
    assert mig.upgrade(conn, migrations) == [m.version for m in migrations]
    assert mig.pending(conn, migrations) == []
    mig.downgrade(conn, migrations, steps=len(migrations))
    assert mig.is_empty_database(conn)
    mig.upgrade(conn, migrations)
    assert mig.current_version(conn) == len(migrations)


def test_modified_applied_migration_is_detected(tmp_path: Path) -> None:
    d = tmp_path / "m"
    d.mkdir()
    (d / "0001_a.up.sql").write_text("CREATE TABLE a (x);")
    conn = connect(tmp_path / "x.db")
    mig.upgrade(conn, mig.discover(d))
    (d / "0001_a.up.sql").write_text("CREATE TABLE a (y);")
    with pytest.raises(mig.MigrationError):
        mig.pending(conn, mig.discover(d))


def test_failed_migration_rolls_back(tmp_path: Path) -> None:
    d = tmp_path / "m"
    d.mkdir()
    (d / "0001_a.up.sql").write_text("CREATE TABLE a (x);\nINSERT INTO missing VALUES (1);")
    conn = connect(tmp_path / "x.db")
    with pytest.raises(sqlite3.OperationalError):
        mig.upgrade(conn, mig.discover(d))
    assert mig.is_empty_database(conn)
    assert mig.current_version(conn) == 0


def test_existing_db_is_not_migrated_implicitly(tmp_path: Path) -> None:
    d = tmp_path / "m"
    d.mkdir()
    (d / "0001_a.up.sql").write_text("CREATE TABLE a (x);")
    conn = connect(tmp_path / "x.db")
    mig.prepare_database(conn, d, auto_migrate=False)  # fresh DB: initialised
    (d / "0002_b.up.sql").write_text("CREATE TABLE b (x);")
    with pytest.raises(MigrationRequiredError):
        mig.prepare_database(conn, d, auto_migrate=False)
    assert mig.prepare_database(conn, d, auto_migrate=True) == [2]


def test_data_dir_inside_repo_is_refused() -> None:
    with pytest.raises(DataBoundaryError):
        ensure_data_dir(Settings(local_data_dir=REPO_ROOT / "PersonalProductivityData"))
    with pytest.raises(DataBoundaryError):
        ensure_data_dir(Settings(local_data_dir=REPO_ROOT.parent))


def test_data_dir_is_owner_only(tmp_path: Path) -> None:
    root = ensure_data_dir(Settings(local_data_dir=tmp_path / "d"))
    assert not POSIX_MODES or oct(root.stat().st_mode & 0o777) == "0o700"
    assert (root / "documents").is_dir()
