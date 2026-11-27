#!/usr/bin/env python3
"""Install Personal OS on this machine — Windows, macOS or Linux.

    python scripts/install.py [--data-dir DIR] [--demo] [--no-env]

Needs only Python 3.10 or newer. Node.js is needed only when the web app has
not been built yet (a ready-made bundle from CI already contains it).

- creates .venv and installs the hash-locked Python dependencies
- builds the web app if it is missing and Node.js 20+ is available
- sets the data folder (default: PersonalProductivityData in your home) in .env
- optionally creates a demo workspace
Nothing is sent anywhere except the package downloads; your data stays local.
"""

from __future__ import annotations

import argparse
import os
import shutil
import subprocess
import sys
import venv
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
WINDOWS = os.name == "nt"


def say(msg: str) -> None:
    print(f"▸ {msg}", flush=True)


def fail(msg: str) -> None:
    print(f"✗ {msg}", file=sys.stderr)
    sys.exit(1)


def run(args: list[str], cwd: Path = ROOT) -> None:
    result = subprocess.run(args, cwd=cwd, check=False)  # noqa: S603 - fixed commands
    if result.returncode != 0:
        fail(f"command failed: {' '.join(args)}")


def venv_bin(venv_dir: Path, name: str) -> Path:
    if WINDOWS:
        return venv_dir / "Scripts" / f"{name}.exe"
    return venv_dir / "bin" / name


def web_built() -> bool:
    return (ROOT / "apps" / "web" / "dist" / "index.html").exists()


def build_web() -> None:
    node = shutil.which("node")
    npm = shutil.which("npm.cmd" if WINDOWS else "npm") or shutil.which("npm")
    if not node or not npm:
        fail(
            "The web app is not built and Node.js is not installed.\n"
            "  Easiest: download the ready-made bundle (personal-os-bundle) from the\n"
            "  repository's Actions page, unzip it and run this script again — it needs\n"
            "  only Python. Or install Node.js 20+ (https://nodejs.org/)."
        )
    out = subprocess.run([node, "-p", "process.versions.node"], capture_output=True, text=True)  # noqa: S603
    if int((out.stdout or "0").split(".")[0] or 0) < 20:
        fail("Node.js 20 or newer is required to build the web app")
    say("Building the web app")
    web = ROOT / "apps" / "web"
    run([npm, "ci", "--no-audit", "--no-fund", "--silent"], cwd=web)
    run([npm, "run", "build", "--silent"], cwd=web)


def write_env(data_dir: Path) -> None:
    env = ROOT / ".env"
    lines = env.read_text(encoding="utf-8").splitlines() if env.exists() else []
    if any(line.startswith("PPOS_LOCAL_DATA_DIR=") for line in lines):
        say("Keeping the data folder already set in .env")
        return
    with env.open("a", encoding="utf-8") as f:
        f.write(f"PPOS_LOCAL_DATA_DIR={data_dir}\n")
    say(f"Data folder: {data_dir} (saved in .env)")


def main() -> None:
    p = argparse.ArgumentParser(description="Install Personal OS on this machine.")
    p.add_argument("--data-dir", type=Path, default=Path.home() / "PersonalProductivityData")
    p.add_argument("--demo", action="store_true", help="also create a demo workspace")
    p.add_argument("--no-env", action="store_true", help="do not write the data folder to .env")
    p.add_argument("--venv", type=Path, default=Path(os.environ.get("PPOS_VENV", ROOT / ".venv")))
    a = p.parse_args()

    if sys.version_info < (3, 10):  # noqa: UP036 - runs before the venv exists
        fail("Python 3.10 or newer is required (https://www.python.org/downloads/)")
    say(f"Using Python {sys.version.split()[0]}")

    py = venv_bin(a.venv, "python")
    if not py.exists():
        say(f"Creating virtual environment in {a.venv}")
        venv.create(a.venv, with_pip=True)
    say("Installing Python dependencies (pinned, hash-checked)")
    uv = shutil.which("uv")
    if uv:
        run(
            [
                uv,
                "pip",
                "install",
                "-q",
                "--python",
                str(py),
                "--require-hashes",
                "-r",
                "requirements.lock",
            ]
        )
        run([uv, "pip", "install", "-q", "--python", str(py), "--no-deps", "-e", "."])
    else:
        run([str(py), "-m", "pip", "install", "-q", "--upgrade", "pip"])
        run([str(py), "-m", "pip", "install", "-q", "--require-hashes", "-r", "requirements.lock"])
        run([str(py), "-m", "pip", "install", "-q", "--no-deps", "-e", "."])

    if web_built():
        say("Web app already built — Node.js not needed")
    else:
        build_web()

    data_dir = a.data_dir.expanduser()
    if not a.no_env:
        write_env(data_dir)
    ppos = venv_bin(a.venv, "ppos")
    run([str(ppos), "--data-dir", str(data_dir), "doctor"])
    demo_dir = Path.home() / "PersonalProductivityDemo"
    if a.demo:
        say(f"Creating a demo workspace in {demo_dir}")
        subprocess.run([str(ppos), "--data-dir", str(demo_dir), "demo"], check=False)  # noqa: S603

    print(f"""
✓ Personal OS is installed.

  Start it:          {ppos} serve --open
  Then, in Chrome or Edge, choose "Install Personal OS" from the address bar
  to get it as an app in your dock / start menu.

  Local AI (optional): Settings → Local AI, e.g. http://127.0.0.1:8080/v1
  Encrypted backup:    {ppos} backup --encrypt""")
    if a.demo:
        print(f"  Demo workspace:      {ppos} --data-dir {demo_dir} serve --open")


if __name__ == "__main__":
    main()
