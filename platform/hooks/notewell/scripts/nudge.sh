#!/usr/bin/env bash
# Stop hook: closing-loop nudge for the notewell repo.
# Thin wrapper — all logic lives in org/scripts/ask_once.py (same entrypoint
# as the workspace-shared ask-once hook) with a REPO=notewell env var so the
# Python logic can apply notewell-specific signal checks.
#
# Signals checked (notewell-specific, beyond the shared baseline):
#   1. A PR is open and code_refs files were modified but the atlas node was
#      not updated this session.
#   2. A test file was added with no corresponding source change (orphan test).
#
# Exits 0 (silent) for the overwhelming majority of Stop events where no
# signal fires. At most one question per session (session memo); 7-day
# per-signal skip-cache.

set -euo pipefail

PROJECT_DIR="${CLAUDE_PROJECT_DIR:-${CURSOR_PROJECT_DIR:-${FACTORY_PROJECT_DIR:-$PWD}}}"

WORKSPACE="$PROJECT_DIR"
while [ "$WORKSPACE" != "/" ] && [ ! -f "$WORKSPACE/repos.yaml" ]; do
  WORKSPACE="$(dirname "$WORKSPACE")"
done
[ -f "$WORKSPACE/repos.yaml" ] || exit 0

export EGZAKTA_PROJECT_DIR="$PROJECT_DIR"
export REPO="notewell"
cd "$WORKSPACE"
exec uv run --quiet --project "$WORKSPACE/org" python \
  "$WORKSPACE/org/scripts/ask_once.py" "$@"
