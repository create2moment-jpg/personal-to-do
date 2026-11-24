#!/usr/bin/env bash
# Install the pre-commit hook that enforces the private-data boundary,
# and set the repository-local commit author (name only; supply your own email).
set -euo pipefail
root="$(git rev-parse --show-toplevel)"
hook="$root/.git/hooks/pre-commit"
cat > "$hook" <<'HOOK'
#!/usr/bin/env bash
set -e
root="$(git rev-parse --show-toplevel)"
python3 "$root/scripts/check_repo_safety.py"
HOOK
chmod +x "$hook"
echo "installed $hook"

git config user.name "${PPOS_GIT_AUTHOR_NAME:-Jimmy}"
if [[ -n "${PPOS_GIT_AUTHOR_EMAIL:-}" ]]; then
  git config user.email "$PPOS_GIT_AUTHOR_EMAIL"
fi
echo "commit author: $(git config user.name) <$(git config user.email || echo 'unset')>"
