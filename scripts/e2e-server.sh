#!/usr/bin/env bash
# Start the app on a throwaway demo workspace for end-to-end tests.
# Never touches your real LOCAL_DATA_DIR. A deterministic fake local LLM
# (scripts/fake_llm.py, 127.0.0.1 only) backs the "Improve with AI" flow.
set -euo pipefail
root="$(cd "$(dirname "$0")/.." && pwd)"
ppos="${PPOS_BIN:-$root/.venv/bin/ppos}"
command -v "$ppos" >/dev/null 2>&1 || ppos=ppos
python="${PYTHON:-python3}"
data="$(mktemp -d "${TMPDIR:-/tmp}/ppos-e2e-XXXXXX")"
llm_port="${PPOS_E2E_LLM_PORT:-11999}"
# Fail loudly if a stale fake model already holds the port (it would answer with old code).
if "$python" -c "import socket,sys; s=socket.socket(); sys.exit(s.connect_ex(('127.0.0.1', $llm_port)) != 0)"; then
  echo "port $llm_port is already in use — stop the old fake_llm.py first" >&2
  exit 1
fi
"$python" "$root/scripts/fake_llm.py" "$llm_port" &
trap 'kill %1 2>/dev/null || true' EXIT
"$ppos" --data-dir "$data" demo >/dev/null
PPOS_LLM_PROVIDER=ollama PPOS_LLM_MODEL=fake-llm PPOS_LLM_BASE_URL="http://127.0.0.1:$llm_port" \
  "$ppos" --data-dir "$data" serve --port "${PPOS_E2E_PORT:-8799}"
