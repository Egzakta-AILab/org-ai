#!/usr/bin/env bash
# Stop hook: the closing-loop ask-once nudge. Thin wrapper — all logic lives in
# org/scripts/ask_once.py where we can reuse the atlas / users / linear helpers.
#
# The hook payload (session_id, transcript_path, cwd) arrives as JSON on stdin;
# `exec` preserves it for the Python entrypoint. stdout must stay clean: either
# empty (no signal → allow stop) or a single Stop-decision JSON object. uv writes
# progress to stderr, and --quiet keeps stdout pristine regardless.
#
# CLAUDE_PROJECT_DIR / CURSOR_PROJECT_DIR / FACTORY_PROJECT_DIR all point at the
# project the dev is working in; we walk up from there to the workspace root
# (the dir that owns repos.yaml + the `org` CLI). If there's no workspace above
# us, this isn't an egzakta session — exit clean and stay silent.

set -euo pipefail

PROJECT_DIR="${CLAUDE_PROJECT_DIR:-${CURSOR_PROJECT_DIR:-${FACTORY_PROJECT_DIR:-$PWD}}}"

WORKSPACE="$PROJECT_DIR"
while [ "$WORKSPACE" != "/" ] && [ ! -f "$WORKSPACE/repos.yaml" ]; do
  WORKSPACE="$(dirname "$WORKSPACE")"
done
[ -f "$WORKSPACE/repos.yaml" ] || exit 0

# Tell the entrypoint where the dev was actually working (git signals run there);
# find_workspace_root() resolves the rest from the workspace cwd.
export EGZAKTA_PROJECT_DIR="$PROJECT_DIR"
cd "$WORKSPACE"
exec uv run --quiet --project "$WORKSPACE/org" python "$WORKSPACE/org/scripts/ask_once.py" "$@"
