#!/usr/bin/env bash
#
# atlas-pre-commit.sh — git pre-commit hook for the egzakta-org meta-repo.
#
# Runs `org atlas validate --strict` ONLY when the staged changes touch
# `atlas/*.md`. Other commits pass through immediately. Keeps the hook
# noiseless on workspace-wide work that doesn't edit the knowledge graph.
#
# Install (run once per clone, from the repo root):
#
#   ln -sf "$(pwd)/org/scripts/atlas-pre-commit.sh" .git/hooks/pre-commit
#   chmod +x .git/hooks/pre-commit
#
# Uninstall:
#
#   rm .git/hooks/pre-commit
#
# To bypass intentionally on a single commit (e.g. work-in-progress with a
# known-broken atlas), use `git commit --no-verify`. Don't make this routine.

set -euo pipefail

# Identify staged atlas/* edits. `--diff-filter=ACM` covers added / copied /
# modified (skip deletes — they can't break frontmatter parsing on their own).
staged_atlas=$(git diff --cached --name-only --diff-filter=ACM | grep -E '^atlas/.*\.md$' || true)

if [ -z "$staged_atlas" ]; then
    exit 0
fi

# Resolve the workspace root (where this script lives, two levels up).
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
WORKSPACE_ROOT="$(cd "$SCRIPT_DIR/../.." && pwd)"

# Prefer a workspace-pinned `org` (uv-installed from ./org); fall back to PATH.
if [ -x "$WORKSPACE_ROOT/org/.venv/bin/org" ]; then
    ORG_BIN="$WORKSPACE_ROOT/org/.venv/bin/org"
elif command -v org >/dev/null 2>&1; then
    ORG_BIN="org"
else
    echo "atlas-pre-commit: \`org\` CLI not found. Install with: uv tool install --editable ./org" >&2
    exit 1
fi

echo "atlas-pre-commit: validating $(echo "$staged_atlas" | wc -l | tr -d ' ') changed atlas file(s)…"

if ! "$ORG_BIN" atlas validate --strict; then
    echo
    echo "atlas-pre-commit: validation failed. Fix the issues above (or commit with \`--no-verify\` if intentional)."
    exit 1
fi

exit 0
