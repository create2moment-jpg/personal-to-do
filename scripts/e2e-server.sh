#!/usr/bin/env bash
# Start the app on a throwaway demo workspace for end-to-end tests.
# Never touches your real LOCAL_DATA_DIR.
set -euo pipefail
root="$(cd "$(dirname "$0")/.." && pwd)"
ppos="${PPOS_BIN:-$root/.venv/bin/ppos}"
command -v "$ppos" >/dev/null 2>&1 || ppos=ppos
data="$(mktemp -d "${TMPDIR:-/tmp}/ppos-e2e-XXXXXX")"
"$ppos" --data-dir "$data" demo >/dev/null
exec "$ppos" --data-dir "$data" serve --port "${PPOS_E2E_PORT:-8799}"
