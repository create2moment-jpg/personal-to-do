import importlib.util
from pathlib import Path

from ppos.infrastructure.config import REPO_ROOT

spec = importlib.util.spec_from_file_location("crs", REPO_ROOT / "scripts" / "check_repo_safety.py")
assert spec and spec.loader
crs = importlib.util.module_from_spec(spec)
spec.loader.exec_module(crs)


def test_forbidden_paths(tmp_path: Path) -> None:
    for rel in [
        "ppos.sqlite3",
        "notes/x.db",
        ".env",
        "PersonalProductivityData/a.md",
        "report.pdf",
    ]:
        assert crs.check_file(rel, tmp_path), rel
    for rel in [".env.example", "fixtures/sample.pdf", "src/app.py"]:
        assert not crs.check_file(rel, tmp_path), rel


def test_secret_and_sqlite_content(tmp_path: Path) -> None:
    fake = "abcdefghij" * 3  # assembled at runtime so this file passes the guard itself
    (tmp_path / "a.py").write_text("API_" + 'KEY = "' + fake + '"\n')
    (tmp_path / "b.txt").write_text("SQLite format 3\x00...")
    (tmp_path / "c.py").write_text("x = 1\n")
    assert crs.check_file("a.py", tmp_path)
    assert crs.check_file("b.txt", tmp_path)
    assert not crs.check_file("c.py", tmp_path)


def test_large_file(tmp_path: Path) -> None:
    (tmp_path / "big.json").write_bytes(b"0" * (crs.MAX_BYTES + 1))
    assert crs.check_file("big.json", tmp_path)
