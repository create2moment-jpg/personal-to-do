#!/usr/bin/env bash
# One-command install of Personal OS on this machine (macOS / Linux / WSL).
#
#   bash scripts/install.sh [--data-dir DIR] [--demo] [--no-env]
#
# - checks Python >= 3.10 and Node >= 20
# - creates .venv and installs the hash-locked Python dependencies
# - builds the web app
# - sets LOCAL_DATA_DIR (default ~/PersonalProductivityData) in .env unless --no-env
# - optionally creates a demo workspace in ~/PersonalProductivityDemo
# Nothing is sent anywhere; your data stays in the data folder.
set -euo pipefail
root="$(cd "$(dirname "$0")/.." && pwd)"
cd "$root"
venv="${PPOS_VENV:-$root/.venv}"
data_dir="$HOME/PersonalProductivityData"
demo=0
write_env=1
while [ $# -gt 0 ]; do
  case "$1" in
    --data-dir) data_dir="$2"; shift 2 ;;
    --demo) demo=1; shift ;;
    --no-env) write_env=0; shift ;;
    -h|--help) sed -n '2,12p' "$0"; exit 0 ;;
    *) echo "unknown option: $1" >&2; exit 2 ;;
  esac
done

say() { printf '\033[1m▸ %s\033[0m\n' "$*"; }
fail() { printf '\033[31m✗ %s\033[0m\n' "$*" >&2; exit 1; }

# --- prerequisites ---------------------------------------------------------
python=""
for candidate in python3.13 python3.12 python3.11 python3.10 python3; do
  if command -v "$candidate" >/dev/null 2>&1 && "$candidate" -c 'import sys; sys.exit(sys.version_info < (3, 10))'; then
    python="$candidate"; break
  fi
done
[ -n "$python" ] || fail "Python 3.10 or newer is required (https://www.python.org/downloads/)"
command -v node >/dev/null 2>&1 || fail "Node.js 20 or newer is required (https://nodejs.org/)"
node -e 'process.exit(Number(process.versions.node.split(".")[0]) >= 20 ? 0 : 1)' || fail "Node.js 20 or newer is required"
say "Using $($python --version) and Node $(node --version)"

# --- Python ----------------------------------------------------------------
if [ ! -x "$venv/bin/python" ]; then
  say "Creating virtual environment in $venv"
  "$python" -m venv "$venv"
fi
say "Installing Python dependencies (pinned, hash-checked)"
if command -v uv >/dev/null 2>&1; then
  uv pip install -q --python "$venv/bin/python" --require-hashes -r requirements.lock
  uv pip install -q --python "$venv/bin/python" --no-deps -e .
else
  "$venv/bin/pip" install -q --upgrade pip
  "$venv/bin/pip" install -q --require-hashes -r requirements.lock
  "$venv/bin/pip" install -q --no-deps -e .
fi

# --- web app ---------------------------------------------------------------
say "Building the web app"
(cd apps/web && npm ci --no-audit --no-fund --silent && npm run build --silent >/dev/null)

# --- data folder -----------------------------------------------------------
if [ "$write_env" = 1 ]; then
  if [ -f .env ] && grep -q '^PPOS_LOCAL_DATA_DIR=' .env; then
    say "Keeping the data folder already set in .env"
  else
    echo "PPOS_LOCAL_DATA_DIR=$data_dir" >> .env
    say "Data folder: $data_dir (saved in .env)"
  fi
fi
"$venv/bin/ppos" --data-dir "$data_dir" doctor

if [ "$demo" = 1 ]; then
  say "Creating a demo workspace in ~/PersonalProductivityDemo"
  "$venv/bin/ppos" --data-dir "$HOME/PersonalProductivityDemo" demo || true
fi

cat <<DONE

$(printf '\033[32m✓ Personal OS is installed.\033[0m')

  Start it:          $venv/bin/ppos serve --open
  Then, in Chrome or Edge, choose "Install Personal OS" from the address bar
  to get it as an app in your dock / start menu.

  Local AI (optional): Settings → Local AI, e.g. http://127.0.0.1:8080/v1
  Encrypted backup:    $venv/bin/ppos backup --encrypt
$( [ "$demo" = 1 ] && echo "  Demo workspace:      $venv/bin/ppos --data-dir ~/PersonalProductivityDemo serve --open" )
DONE
