#!/usr/bin/env python3
"""Data-boundary guard: refuse commits that could contain private data or secrets.

Stdlib only so it runs as a Git pre-commit hook without the app installed.

    python scripts/check_repo_safety.py            # check staged files (pre-commit)
    python scripts/check_repo_safety.py --all      # check every tracked file (CI)
    python scripts/check_repo_safety.py FILE...    # check specific files

Allow-list a deliberate exception by adding its path to
``config/repo-safety-allowlist.txt`` (one glob per line) with a review.
"""

from __future__ import annotations

import argparse
import fnmatch
import re
import subprocess
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
ALLOWLIST = REPO_ROOT / "config" / "repo-safety-allowlist.txt"
MAX_BYTES = 2 * 1024 * 1024

# Private runtime artefacts that must never be committed.
FORBIDDEN_GLOBS = [
    "*.sqlite", "*.sqlite3", "*.db", "*.db-wal", "*.db-shm", "*.sqlite3-wal", "*.sqlite3-shm",
    "*.npy", "*.npz", "*.faiss", "*.index", "*.parquet", "*.pkl", "*.pickle",
    "*.tar.gz", "*.tgz", "*.zip", "*.bak",
    ".env", ".env.*", "*.pem", "*.key", "*.p12", "*.pfx", "id_rsa*", "id_ed25519*",
    "PersonalProductivityData/*", "*/PersonalProductivityData/*", "local_data/*", "data/*",
    "*.docx", "*.xlsx", "*.pptx", "*.pdf",
]  # fmt: skip
ALLOWED_GLOBS = [".env.example", "fixtures/*", "tests/fixtures/*", "docs/*.pdf"]

SECRET_PATTERNS = [
    ("private key", re.compile(r"-----BEGIN [A-Z ]*PRIVATE KEY-----")),
    ("AWS access key", re.compile(r"\bAKIA[0-9A-Z]{16}\b")),
    ("GitHub token", re.compile(r"\bgh[pousr]_[A-Za-z0-9]{36,}\b")),
    ("Slack token", re.compile(r"\bxox[abposr]-[A-Za-z0-9-]{10,}\b")),
    ("API key assignment", re.compile(
        r"""(?i)\b(api[_-]?key|secret|token|password)\b\s*[:=]\s*["'][A-Za-z0-9_\-/+=]{16,}["']"""
    )),
    ("OpenAI/Anthropic style key", re.compile(r"\bsk-(?:ant-)?[A-Za-z0-9_-]{20,}\b")),
]  # fmt: skip


def _git(*args: str) -> list[str]:
    out = subprocess.run(  # noqa: S603 - fixed git invocation, no shell
        ["git", *args],  # noqa: S607
        cwd=REPO_ROOT,
        capture_output=True,
        text=True,
        check=True,
    ).stdout
    return [line for line in out.splitlines() if line]


def _matches(path: str, globs: list[str]) -> bool:
    name = Path(path).name
    return any(fnmatch.fnmatch(path, g) or fnmatch.fnmatch(name, g) for g in globs)


def _allowlist() -> list[str]:
    if not ALLOWLIST.exists():
        return []
    lines = ALLOWLIST.read_text(encoding="utf-8").splitlines()
    return [ln.strip() for ln in lines if ln.strip() and not ln.startswith("#")]


def check_file(
    rel: str, root: Path = REPO_ROOT, extra_allowed: list[str] | None = None
) -> list[str]:
    problems: list[str] = []
    allowed = ALLOWED_GLOBS + (extra_allowed or [])
    if _matches(rel, FORBIDDEN_GLOBS) and not _matches(rel, allowed):
        problems.append(f"{rel}: file type/location looks like private runtime data")
    path = root / rel
    if not path.is_file():
        return problems
    size = path.stat().st_size
    if size > MAX_BYTES and not _matches(rel, allowed):
        problems.append(
            f"{rel}: {size} bytes exceeds {MAX_BYTES} (large data does not belong in Git)"
        )
        return problems
    try:
        text = path.read_text(encoding="utf-8")
    except (UnicodeDecodeError, OSError):
        return problems
    if text.startswith("SQLite format 3"):
        problems.append(f"{rel}: SQLite database content")
    if rel.endswith("check_repo_safety.py"):
        return problems  # this file necessarily contains the patterns
    for label, pattern in SECRET_PATTERNS:
        if pattern.search(text):
            problems.append(f"{rel}: possible {label}")
    return problems


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("files", nargs="*")
    parser.add_argument("--all", action="store_true", help="check all tracked files")
    args = parser.parse_args(argv)

    if args.files:
        files = args.files
    elif args.all:
        files = _git("ls-files")
    else:
        files = _git("diff", "--cached", "--name-only", "--diff-filter=ACMR")

    extra = _allowlist()
    problems = [p for f in files for p in check_file(f, extra_allowed=extra)]
    if problems:
        print("Repository safety check FAILED — possible private data or secrets:", file=sys.stderr)
        for p in problems:
            print(f"  - {p}", file=sys.stderr)
        print("Private data belongs in LOCAL_DATA_DIR, outside the repository.", file=sys.stderr)
        return 1
    print(f"repository safety check passed ({len(files)} files)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
