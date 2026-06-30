# Working on a Linear ticket — end-to-end loop

The canonical workflow for moving a Linear ticket to a merged PR. Exercises the three things that make the workspace more than a folder of repos: the `linear` skill (ticket I/O), the `atlas` skill (product grounding), and the per-repo agents installed by `org install`.

Same loop for every repo on the platform — skills and agents adapt per-repo via their installed config.

---

## TL;DR

```bash
# 1. Pick a ticket.
linear issues list --assigned                       # or open the ticket URL.

# 2. Ground in the atlas if the ticket carries an `atlas:` label.
org atlas show capability.search.hybrid-retrieval

# 3. Branch via worktree (creates `<repo>/.worktrees/nw-NNN/` on `$LINEAR_HANDLE/nw-NNN`).
org worktree create NW-NNN                        # auto-detects repos from atlas labels
cd notewell/.worktrees/nw-NNN                        # work happens here

# 4. Implement (in an agent session): linear skill → atlas skill → notewell-tdd-implementer.

# 5. Self-review.
/review-2axis

# 6. Push, open PR.
git push -u origin "$LINEAR_HANDLE/nw-NNN"
gh pr create --base main --title "…" --body "…"

# 7. Comment back on Linear.
linear issues comment add NW-NNN -m "PR opened: <url>"
```

Or just run `/work-ticket NW-NNN` in notewell — the slash command automates steps 1-3 and assembles the dispatch brief for step 4.

---

## 1. Pick a ticket

The `linear` skill is the single interface for ticket I/O. Installed globally via `org install --global`, so every agent on every repo has it.

```bash
linear issues list --assigned --project "Workspace Platform"
linear issues view NW-435
```

In an agent session, paste the ticket URL and ask "pull NW-NNN and tell me what it needs" — the skill handles title, description, status, labels, project, comments.

Needs `LINEAR_API_KEY` in your environment. See the skill's README for issuing a personal key. The engine never reads or copies the key.

---

## 2. Atlas grounding

If the ticket carries `atlas:<node-id>`, the author is saying "this work touches this capability." **Always** ground before planning:

```bash
org atlas show capability.search.hybrid-retrieval
```

What to extract from the output:

- **`code_refs`** — workspace paths to implementing code. Read before proposing changes; usually where the change goes.
- **`depends_on`** — capabilities this one needs. If your change touches anything here, blast radius is wider than the ticket suggests.
- **`unlocks`** — what depends on THIS. Breaking changes ripple outward; flag in the PR.
- **`linear`** — the canonical project for this node. Should match the ticket's project; if not, the label is wrong — flag it before starting.
- **Body** — the "why it matters" and "current state at notewell" the ticket usually omits.

If the ticket lacks an `atlas:` label but obviously touches a capability: add the label via the linear skill, or note the matching node in the PR description so a reviewer can backfill.

`org atlas show` works in CI/hooks/headless loops; `obsidian-cli` requires the desktop app open — use it only when actually browsing the vault.

---

## 3. Branch — `org worktree create`

```bash
org worktree create NW-NNN                        # auto-detects affected repos from atlas labels
org worktree create NW-NNN --repos notewell,infra # or pick them explicitly
org worktree list                                   # see who's working on what across the workspace
org worktree drop NW-NNN                          # clean up after merge
```

For each affected repo, `create` makes a worktree at `<repo>/.worktrees/nw-NNN/` on branch `$LINEAR_HANDLE/nw-NNN`. Cross-repo tickets get one worktree per affected repo — every agent and IDE works in isolation, no branch-juggling between tickets.

**Repo auto-detection** walks each `atlas:<node-id>` label on the ticket, looks up the atlas node, and unions the first path segment of every `code_refs` entry. So a ticket labeled `atlas:capability.search.hybrid-retrieval` plus `atlas:platform.storage` gets worktrees in both `notewell/` and `infra/` automatically. Override with `--repos R,R` when the atlas labels don't yet exist.

**Soft Linear claim**: `create` posts a `🔒 org-worktree: claimed by @<handle>` comment on the ticket and refuses a second `create` from another shell within 24h (unless `--force`). Stops two agents from grabbing the same ticket. Skip it with `--no-claim` for local exploration.

Branch name MUST be `<your-linear-handle>/nw-NNN` (the worktree command builds it for you) — that's how Linear auto-links PRs. Set `LINEAR_HANDLE` once in your shell rc (your Linear username, lowercase). See [docs/setup.md](setup.md) — every teammate sets their own. `LINEAR_API_KEY` is needed for the claim + auto-detect; without it, `create` falls back to notewell with a warning.

**Never** put `NW-NNN` in code, docstrings, comments, or repo-level docs. Linear IDs belong in the PR title/description (auto-linked), the branch name (auto-linked), and optionally the commit message. Implementation deviation notes go on the Linear ticket as comments.

---

## 4. Implement

**Pre-implementation checklist** — each item below has been a real failure mode at least once:

- **Atlas context in the dispatch turn.** If the ticket carries `atlas:<node-id>`, paste `org atlas show <node-id>` output into the same turn that briefs the implementer. The standard says the implementer MUST halt if it doesn't see atlas context for a labeled ticket.
- **Grill artifact if `complexity:high`.** Run `/grill-with-docs` to interrogate the design BEFORE briefing the implementer. The grill writes a `## Decisions` section onto the relevant atlas node body; you review and commit the patch yourself (grill never auto-commits). The implementer halts on missing grill for `complexity:high` — see `platform/standards/_shared/instructions.md`.
- **Runtime versions match any pinned config.** Check `pyproject.toml`, `pyrefly.toml`, `package.json#engines`. Python: `cd backend && poetry env info | grep "Python "`. Node: `node --version`. Mismatch → align FIRST.
- **Working tree clean for in-scope files.** Untracked junk in unrelated paths is fine; uncommitted edits to files the agent will touch will confuse the diff and the review pass.

### Dispatching the implementer

For notewell, `org install --repo notewell` installs the relevant agents:

- `notewell-tdd-implementer` — the only agent with write access. TDD-first: tests then implementation.
- `notewell-orchestrator` — review entry point. Dispatches reviewers in parallel based on the diff.
- Six reviewer agents (Python backend, backend tests, frontend code, frontend tests, API contract, security) — read-only, persist outputs to `.reviews/`.

**Claude Code:**

```
> /notewell-tdd-implementer

Implement NW-410.

Atlas context (capability.search.hybrid-retrieval):
[paste org atlas show output here]

Ticket scope: pyrefly.toml config + baseline + hook library entry point.
Start with failing tests, stop after first green pass for review.
```

If the slash command doesn't dispatch in your build, fall back to a general-purpose agent pointed at the agent file:

```
> Spawn a general-purpose agent with this brief:
> "You are notewell-tdd-implementer per notewell/.claude/agents/notewell-tdd-implementer.md.
> Read that file and notewell/CLAUDE.md, then follow the role + standards exactly.
> Implement NW-410. [Atlas context + scope + plan as above]"
```

**Cursor:** invoke as `@notewell-tdd-implementer` in chat. **Factory droid:** invoke directly as `/notewell-tdd-implementer` — droids ARE the slash-command surface.

---

## 5. Self-review

For notewell changes, the heavyweight specialist pass:

```
> /review-2axis
```

Invokes `notewell-orchestrator`, which:

1. Computes diff scope (branch vs `main` via `git merge-base`).
2. Maps changed files to reviewer agents.
3. Dispatches them in parallel.
4. Pipes outputs through `notewell-consolidator` (dedupes, surfaces conflicts).

For non-notewell repos (infra, legacy-wiki, search-lab), or for a quick two-axis read on any change:

```
> /review-2axis main
```

Runs two parallel sub-agents — Standards (vs `platform/standards/`, `CLAUDE.md`, `atlas/ontology.md`) and Spec (vs the Linear ticket + atlas node `## Decisions` + grill artifact). Reports are deliberately UNMERGED — one axis can't mask the other. You can run both in the same session.

Before stopping for the day (or context-compacting), `/handoff` writes a worktree-local handoff doc so a fresh session resuming in the same worktree picks up cold.

Outputs land at `.reviews/<run-id>/` (gitignored). Read the consolidated file and fix what's flagged before pushing.

---

## 6. Push, open PR

```bash
git push -u origin "$LINEAR_HANDLE/nw-NNN"
gh pr create --base main \
  --title "Short imperative title (no NW prefix; Linear adds it)" \
  --body-file /tmp/pr-body.md
```

The PR body must be self-contained — anyone reading it a year from now should understand the change without context. Don't say "as discussed in NW-NNN".

---

## 7. Close the loop in Linear

```bash
linear issues comment add NW-NNN -m "PR opened: <pr-url>"
# When merged:
linear issues update NW-NNN -s "Done"
```

If the work changed a capability's behavior (status, metrics, code_refs), **also update the atlas node** in a tiny follow-up commit to the meta-repo. `org atlas validate` before committing.

---

## The closing nudge (ask-once hook)

A workspace-shared `Stop` hook closes the loop for you: at the end of a work turn it
may surface **one** question — and only one per session — when a real signal fires.
Install it once (it then resolves from any cwd):

```bash
org install --global --component hooks
```

What it watches (highest priority first; it asks about the first that fires and
isn't already snoozed):

| Signal | Fires when | Asks |
|---|---|---|
| ticket-comment | commits on a `<handle>/nw-NNN` branch ahead of `main` | comment the progress on Linear |
| handoff | session > 60 min **or** ≥ 8 files touched, no handoff written | run `/handoff` |
| atlas-refresh | you touched a file listed in some atlas node's `code_refs` | refresh that node |
| docs-update | new `platform/agents/` or `platform/skills/` assets | update `docs/skills.md` |
| owner-notify | you touched a `capability.*` you don't own | @mention the owner in Linear |

Throttling, so it never nags: **one question per session**; a 7-day per-signal
snooze written the moment it asks (a *different* node/ticket re-fires immediately —
the snooze key carries the discriminator); and **atlas-only sessions never ask**.

Turn it off per-developer in your profile (`platform/profiles/<handle>.yaml`):

```yaml
preferences:
  ask_hook: off        # default is on
```

Debug / reset:

```bash
# Dry-run from inside the workspace: print which signal would fire, emit nothing.
python org/scripts/ask_once.py --dry-run
# Clear all 7-day snoozes:
rm ~/.cache/egzakta-org/skip-cache.json
```

---

## Setup verification

If anything above breaks, run these to localize:

```bash
org atlas validate                       # atlas reader installed
org worktree list                        # worktree primitive responds (empty is fine)
ls ~/.claude/skills/                     # should include atlas, linear, obsidian-cli
ls notewell/.claude/agents/                 # should include notewell-orchestrator etc.
org install --check                      # should report clean
```

A broken loop is worse than no loop — it gives false confidence. Fix drift before starting real work.
