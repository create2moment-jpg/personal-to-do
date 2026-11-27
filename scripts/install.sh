#!/usr/bin/env bash
# One-command install of Personal OS (macOS / Linux / WSL). On Windows run:
#   py scripts\install.py
#
#   bash scripts/install.sh [--data-dir DIR] [--demo] [--no-env]
#
# Needs only Python >= 3.10. Node.js is needed only if the web app is not built
# yet — the ready-made bundle from CI (personal-os-bundle) already contains it.
# See scripts/install.py for what it does. Nothing is sent anywhere.
set -euo pipefail
root="$(cd "$(dirname "$0")/.." && pwd)"
for candidate in python3.13 python3.12 python3.11 python3.10 python3; do
  if command -v "$candidate" >/dev/null 2>&1 && "$candidate" -c 'import sys; sys.exit(sys.version_info < (3, 10))'; then
    exec "$candidate" "$root/scripts/install.py" "$@"
  fi
done
echo "✗ Python 3.10 or newer is required (https://www.python.org/downloads/)" >&2
exit 1
