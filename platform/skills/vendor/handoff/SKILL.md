---
name: handoff
description: >
  Compact the current conversation into a worktree-local handoff document
  so a fresh agent session can resume the ticket without re-establishing
  context. Writes to `<active-worktree>/.handoffs/<ticket>-<iso>.md` —
  worktree-aware on purpose: the next session resuming in the same
  worktree finds it automatically. Use before stopping work, switching
  tickets, or context-compacting.
<!-- tool:claude -->
allowed-tools: Bash, Read, Write
<!-- /tool -->
<!-- tool:cursor,droid -->
allowed-tools: Bash Read Write
<!-- /tool -->
metadata:
  version: "0.1.0"
  triggers:
    - "handoff"
    - "pass this off"
    - "I'm stopping for the day"
    - "compact this"
---

# handoff — worktree-local context transfer

Distil the live conversation into a self-contained document the next agent
can pick up cold. Worktree-local so it travels with the work, not with the
machine.

## When to use

- End of day / pausing the ticket.
- Switching to another ticket (multiple worktrees in play).
- Conversation getting long; before manual context compaction.
- Pairing with a teammate who'll continue tomorrow.

## Argument

`What will the next session focus on?` — optional. If given, emphasise
that direction in the handoff. If omitted, default to "resume the ticket
from where it stands".

## Calibration — read the user's preferred handoff detail

```bash
HANDOFF_DETAIL=$(org user show "$LINEAR_HANDLE" --field preferences.handoff_detail 2>/dev/null || echo medium)
```

Tiers the verbosity:

- **`low`** — ticket id + commits-since-last-handoff + 3-bullet next-step list.
  Under 200 words. For senior devs handing off to themselves.
- **`medium`** (default) — adds atlas refs, open questions, current test
  state, PR URL. 400-600 words. Universal default.
- **`high`** — full context dump including reasoning behind recent decisions,
  alternative approaches considered, partial-work notes. 500-800 words.
  For contractors / distributed teammates / cross-time-zone pickups.

If the user has no profile yet, default to `medium`.

## Procedure

1. **Identify the active worktree.**

   ```bash
   # Determine cwd is inside a worktree by checking for .git file (not .git dir).
   git rev-parse --show-toplevel
   ```

   If the cwd isn't inside a worktree created by `org worktree create`,
   STOP and reply: "I don't see an active worktree. Run `org worktree
   create NW-NNN` first, or move into one of `org worktree list`'s
   entries. The handoff doc is worktree-local so the next session resuming
   in the same worktree picks it up automatically."

2. **Identify the ticket.** Extract from the worktree name
   (`.worktrees/nw-NNN/` → `NW-NNN`) or ask the user.

3. **Build the handoff document.**

   Path: `<worktree-root>/.handoffs/<ticket>-<ISO-timestamp>.md` (timestamp
   in UTC, `YYYYMMDDTHHMMSSZ` form).

   Structure (skip sections that don't apply — empty headers are noise):

   ```markdown
   # Handoff: NW-NNN
   
   _Written: <ISO-timestamp> · Author: $LINEAR_HANDLE_
   
   ## Next session focus
   <what the user said when invoking /handoff, or default>
   
   ## Worktrees in play
   - <repo>: <path-from-workspace-root> on branch `<branch>`
   <one bullet per worktree from `org worktree list --ticket NW-NNN`>
   
   ## Linear
   - URL: https://linear.app/your-team/issue/NW-NNN/
   - State: <state from linear skill if available>
   - Atlas labels: `atlas:<node-id>`, …
   - Most-recent comment summary: <one line, last comment author + gist>
   
   ## Atlas grounding
   - Node(s): <node-id> — link to body
   - `## Decisions` from grill (if grill ran): <link to atlas/<path>.md#decisions>
   
   ## What's been done
   <bullet list of completed work, max 5 bullets, factual>
   
   ## What's pending
   <bullet list, max 5 bullets, ranked by priority for the next session>
   
   ## Open questions
   <questions that came up but were not resolved — for the next session OR
   for the user to think about offline>
   
   ## Test / validator state
   <last-known status: e.g. "pytest: 107/107 pass as of <commit-sha>",
   "/review run: 2 standards findings open in .reviews/<run-id>/">
   
   ## PR (if any)
   - URL
   - State (draft / open / approved / mergeable)
   
   ## Suggested next-skill invocations
   - `/work-ticket NW-NNN` — re-orient and re-verify branches/worktrees
   - `/diagnose` if next session is bug investigation
   - `/grill-with-docs` if mid-design (more branches to walk)
   - `/review` before pushing
   ```

4. **Redact secrets before writing.** Any line that looks like an API key,
   token, password, or path containing `secret`/`credential` — REPLACE with
   `[REDACTED — see skill body of /handoff for policy]`. We never persist
   live credentials, not even in worktree-local files.

5. **Verbosity.** Default is medium detail. If the user supplies an
   argument like `--brief` or `--detailed`, adjust accordingly. (When
   per-user profiles ship — PR3 — read `profile.preferences.handoff_detail`
   for the default.)

6. **Write the file, print the absolute path, and stop.** Do NOT commit
   it. `.handoffs/` should be added to the worktree's `.gitignore` if
   missing — append-once, idempotent:

   ```bash
   if [ -f .gitignore ] && ! grep -qE '^\.handoffs/?$' .gitignore; then
     echo '.handoffs/' >> .gitignore
   fi
   ```

## What this skill does NOT do

- Write to the OS temp dir. (Mattpocock's default; we deviate
  deliberately — worktree-local lets the doc travel with the work.)
- Commit the handoff. It's ephemeral context, not artifact.
- Modify any code or atlas node.
- Persist secrets, ever. Redact on sight.

## References

- Worktree primitive: `org worktree create/list/drop`
- Ticket workflow: `docs/working-on-tickets.md`
- Original concept (adapted): mattpocock/skills/productivity/handoff
