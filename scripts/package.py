#!/usr/bin/env python3
"""Build a ready-to-run bundle: the tracked source plus the built web app.

    python scripts/package.py [--out DIR]

The bundle installs with Python only (`python scripts/install.py`) — no Node.js.
Only files tracked by Git are included (never .env, data or local caches),
plus apps/web/dist, which must be built first (`npm run build` in apps/web).
"""

from __future__ import annotations

import argparse
import shutil
import subprocess
import sys
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "packages"))


def main() -> None:
    p = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    p.add_argument("--out", type=Path, default=ROOT / "build")
    a = p.parse_args()
    dist = ROOT / "apps" / "web" / "dist"
    if not (dist / "index.html").exists():
        sys.exit("apps/web/dist is missing — build the web app first (npm run build)")
    from ppos import __version__

    git = shutil.which("git")
    if git is None:
        sys.exit("git is needed to list the tracked files")
    listed = subprocess.run([git, "ls-files", "-z"], cwd=ROOT, capture_output=True, check=True)  # noqa: S603
    tracked = listed.stdout.decode().split("\0")
    files = sorted({f for f in tracked if f and (ROOT / f).is_file()})
    files += sorted(
        str(f.relative_to(ROOT)) for f in dist.rglob("*") if f.is_file() and f.suffix != ".map"
    )
    a.out.mkdir(parents=True, exist_ok=True)
    name = f"personal-os-{__version__}"
    target = a.out / f"{name}.zip"
    with zipfile.ZipFile(target, "w", zipfile.ZIP_DEFLATED) as z:
        for f in files:
            z.write(ROOT / f, f"{name}/{f}")
    print(f"{target} ({target.stat().st_size // 1024} KB, {len(files)} files)")


if __name__ == "__main__":
    main()
