import json
import tarfile
from pathlib import Path

import pytest

from ppos.bootstrap import Container
from ppos.infrastructure.backup import BackupError, create_backup, export_json, restore_backup
from ppos.infrastructure.config import Settings
from tests.conftest import latest_schema_version


def test_backup_restore_roundtrip(container: Container, settings: Settings, tmp_path: Path) -> None:
    task = container.tasks.create("keep me")
    (settings.local_data_dir / "documents" / "doc.txt").write_text("original")
    info = create_backup(settings)
    assert info.schema_version == latest_schema_version()

    container.tasks.delete(task.id)
    aside = restore_backup(settings, info.path, force=True)
    assert aside is not None and (aside / "db" / "ppos.sqlite3").exists()  # never deleted
    assert container.tasks.get(task.id).title == "keep me"
    assert (settings.local_data_dir / "documents" / "doc.txt").read_text() == "original"
    assert info.path.exists()  # historical backups kept with live data


def test_restore_refuses_to_overwrite_without_force(
    container: Container, settings: Settings
) -> None:
    info = create_backup(settings)
    with pytest.raises(BackupError):
        restore_backup(settings, info.path)


def test_restore_into_empty_dir(container: Container, settings: Settings, tmp_path: Path) -> None:
    container.tasks.create("portable")
    info = create_backup(settings, dest_dir=tmp_path / "out")
    other = Settings(local_data_dir=tmp_path / "fresh")
    assert restore_backup(other, info.path) is None
    from ppos.bootstrap import build_container

    restored = build_container(other)
    assert [
        t.title
        for t in restored.tasks.find(
            __import__("ppos.application.ports", fromlist=["TaskQuery"]).TaskQuery()
        )
    ] == ["portable"]


def test_corrupt_backup_is_rejected(
    container: Container, settings: Settings, tmp_path: Path
) -> None:
    info = create_backup(settings)
    bad = tmp_path / "bad.tar.gz"
    with tarfile.open(info.path) as src, tarfile.open(bad, "w:gz") as dst:
        for m in src.getmembers():
            data = src.extractfile(m)
            if m.name == "manifest.json" and data:
                manifest = json.loads(data.read())
                manifest["files"]["db/ppos.sqlite3"] = "0" * 64
                raw = json.dumps(manifest).encode()
                m.size = len(raw)
                import io

                dst.addfile(m, io.BytesIO(raw))
            else:
                dst.addfile(m, data)
    with pytest.raises(BackupError, match="checksum"):
        restore_backup(Settings(local_data_dir=tmp_path / "x"), bad)


def test_path_traversal_member_rejected(settings: Settings, tmp_path: Path) -> None:
    evil = tmp_path / "evil.tar.gz"
    payload = tmp_path / "p.txt"
    payload.write_text("x")
    with tarfile.open(evil, "w:gz") as tar:
        tar.add(payload, arcname="../escape.txt")
    with pytest.raises(BackupError, match="unsafe"):
        restore_backup(settings, evil)


def test_export_contains_tables(container: Container, settings: Settings) -> None:
    container.tasks.create("exported")
    data = json.loads(export_json(settings).read_text())
    assert data["tables"]["tasks"][0]["title"] == "exported"


def test_export_includes_every_feature(container: Container, settings: Settings) -> None:
    from ppos.demo import seed_demo

    seed_demo(container)
    data = json.loads(export_json(settings).read_text())
    assert data["format"] == 2 and data["schema_version"] >= 12
    tables = data["tables"]
    for name in ("goals", "skills", "skill_ratings", "reviews", "meetings", "meeting_series",
                 "career_expectations", "evidence_links", "facts", "documents", "book_nodes",
                 "sprints", "weekly_plans", "people", "topics"):  # fmt: skip
        assert name in tables, name
    assert tables["goals"] and tables["skills"] and tables["facts"]
    assert "embeddings" not in tables and not any(t.startswith("search_index") for t in tables)
    assert "embeddings" in data["excluded"]
