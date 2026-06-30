#!/usr/bin/env bash
# PostToolUse hook: atlas drift check for the notewell repo.
# Thin wrapper — all logic lives in org/scripts/atlas_drift_check.py where
# we can reuse the atlas / users helpers.
#
# The hook payload (tool_name, tool_input, tool_response, cwd) arrives as JSON
# on stdin; `exec` preserves it for the Python entrypoint. stdout must stay
# clean: either empty (no drift detected → allow tool use) or a single
# PostToolUse-decision JSON object with additionalContext. uv writes progress
# to stderr, and --quiet keeps stdout pristine regardless.
#
# Only fires when the tool wrote or edited a file that appears in any atlas
# node's code_refs. Exits 0 silently for all other tool uses.

set -euo pipefail

PROJECT_DIR="${CLAUDE_PROJECT_DIR:-${CURSOR_PROJECT_DIR:-${FACTORY_PROJECT_DIR:-$PWD}}}"

# Walk up to the workspace root (the dir that owns repos.yaml + the `org` CLI).
WORKSPACE="$PROJECT_DIR"
while [ "$WORKSPACE" != "/" ] && [ ! -f "$WORKSPACE/repos.yaml" ]; do
  WORKSPACE="$(dirname "$WORKSPACE")"
done
[ -f "$WORKSPACE/repos.yaml" ] || exit 0

export EGZAKTA_PROJECT_DIR="$PROJECT_DIR"
cd "$WORKSPACE"
exec uv run --quiet --project "$WORKSPACE/org" python \
  "$WORKSPACE/org/scripts/atlas_drift_check.py" "$@"
