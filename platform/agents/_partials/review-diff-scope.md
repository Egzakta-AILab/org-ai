1. Capture diff scope and a stable run handle:

   ```bash
   BRANCH=$(git rev-parse --abbrev-ref HEAD)
   if [ "$BRANCH" = "main" ]; then BASE="HEAD~1"; else BASE="$(git merge-base HEAD main)"; fi
   SHA=$(git rev-parse --short HEAD); TS=$(date -u +%Y%m%d-%H%M)
   ```

2. `git diff "$BASE"..HEAD --stat` for changed files; `git diff "$BASE"..HEAD` for the full diff.

3. Read `{{R}}{{INSTRUCTIONS_FILE}}` for stack, conventions, project rules.
