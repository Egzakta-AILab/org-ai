---
description: Cross-repo Linear ticket preflight — pull context, ground in atlas, create worktrees in all affected repos, gate on complexity:high, build dispatch template.
argument-hint: <NW-NNN>
allowed-tools: Bash, Read
---

You are starting work on Linear ticket **$ARGUMENTS** in the egzakta workspace. Run the full preflight before any implementation. **Stop after step 7** so the user can review before dispatching the implementer.

This command lives in `platform/commands/_shared/` and is installed user-globally — it runs identically from the workspace root, from inside any sub-repo (notewell, infra, …), and from any sub-dir. Cross-repo tickets are first-class.

---

## Step 1 — Pull the ticket

```bash
cd ~/.claude/skills/linear && npm run query -- 'query { issue(id: "$ARGUMENTS") { id identifier title description state { name } priority labels { nodes { id name } } project { name } } }'
```

Extract: title, state, priority, project, **all labels** (especially `atlas:*` and `complexity:*`), description.

If the ticket doesn't exist or fetch fails, STOP and report — never fabricate context.

---

## Step 2 — Atlas grounding (mandatory if labeled)

Scan labels for `atlas:<node-id>`. **For each one**, run:

```bash
org atlas show <node-id>
```

Extract per node: `code_refs` (files), `depends_on` / `unlocks` (blast radius), `linear.projects` (flag mismatch with ticket's project), `## Decisions` section if any, body.

This is the dispatcher's job, not the implementer's — both the shared standards (`platform/standards/_shared/instructions.md`) and per-repo standards require atlas context in the dispatch turn.

**If no `atlas:` label** but the ticket touches a capability: suggest a candidate via `org atlas list --type capability | grep -i <keyword>`. Don't add the label automatically — note it for the user.

**If `org atlas show` says "not found":** STOP. The label is wrong or the atlas is stale. Report; don't guess.

---

## Step 3 — Resolve target repos

Precedence:

1. **From atlas:** union the first path segment of every `code_refs` entry across all atlas nodes you grounded in step 2. That set is the affected repos.
2. **From ticket body:** if the ticket description has a `repos: [notewell, infra]` line, use that.
3. **From file paths in the description:** grep the description for `<repo>/...` paths matching known repos in `repos.yaml`.
4. **From cwd inference:** if cwd is inside a repo in `repos.yaml`, default to that single repo.
5. **Fallback:** the primary repo, with a one-line warning. Never silently include all repos.

Print the resolved set. If it's empty after all five steps, STOP and ask the user.

---

## Step 4 — Create worktrees

Use the `org worktree` primitive. It handles the soft Linear claim, the cross-repo coordination, and the branch naming.

```bash
TICKET_FULL="$ARGUMENTS"        # e.g. NW-789
REPOS="<comma-separated set from step 3>"

org worktree create "${TICKET_FULL}" --repos "${REPOS}"
```

If `org worktree create` reports an existing claim by another dev, STOP and tell the user. They can override with `--force` only if the other dev has confirmed they're done.

After success, `org worktree list --ticket ${TICKET_FULL}` prints the per-repo paths. Capture them — the dispatch brief in step 6 references them.

---

## Step 5 — Complexity gate

Scan the ticket's labels for `complexity:<level>`.

**If `complexity:high`** — MANDATORY grill. The shared standards halt the implementer until a grill artifact lives on the atlas node body.

```
> Run /grill-with-docs against $ARGUMENTS.
> The grill MUST produce a `## Decisions` patch appended to the atlas node
> body before I assemble the dispatch template in step 6. If grill output
> isn't visible at the end of this command, STOP and tell the user.
```

After grill completes and the user has committed the atlas-node patch, continue.

**If `complexity:medium` or `complexity:low` or no complexity label** — grill is optional. Offer it:

> "Run /grill-with-docs first to stress-test the design? (yes / skip)"

If user says skip, proceed. If yes, run grill, then proceed.

**Standards reference:** `platform/standards/_shared/instructions.md` (shared baseline) and per-repo overrides both halt the implementer on a missing grill artifact for `complexity:high`.

---

## Step 6 — Assemble the dispatch template

Decide WHICH implementer to brief based on the affected-repos set:

- Single repo with a repo-specific implementer (e.g. `notewell` has a `notewell-tdd-implementer`) → use that one.
- Multiple repos OR a repo without a specialist → use the workspace-shared implementer at `~/.claude/agents/workspace-tdd-implementer.md` (fall back to per-repo briefs, one per repo).

Template (per repo when the work spans many):

```
> Spawn a general-purpose agent with this brief:
>
> "You are <implementer>. Read your agent file and the relevant standards
> (CLAUDE.md / AGENTS.md plus platform/standards/_shared/instructions.md).
>
> Implement <NW-NNN>: <ticket title>.
>
> ## Ticket context
> Priority: <P>  Project: <name>  Labels: <comma-separated>
> <ticket description>
>
> ## Atlas grounding
> <one block per atlas:* label, with status, depends_on, unlocks, code_refs,
>  most recent `## Decisions` entries, body summary>
>
> ## Grill artifact (complexity:high)
> Atlas node body section: atlas/<path>.md#decisions (committed in <sha>)
> Decisions:
> <bullet list of decisions from the grill patch>
>
> ## Worktree
> Repo: <name>   Path: <repo>/.worktrees/nw-NNN/   Branch: <handle>/nw-NNN
>
> ## Runtime
> <per-repo check output — only when relevant to this repo>
>
> ## Plan
> Start with failing tests. Stop after first green pass for review."
```

Omit the Grill section when not `complexity:high`. Omit the Atlas section if no `atlas:` label (and add: "No atlas label on this ticket; ground in code yourself.").

---

## Step 7 — Stop and hand back

Print:
1. The full set of created worktrees (paths + branch).
2. The grill artifact location (if grill ran).
3. The assembled dispatch template(s) (fenced; one per repo if multi-repo).
4. `Ready. Paste the brief above to start the implementer, or refine the context first.`

**Do NOT dispatch the implementer yourself.** L2 automation = prep everything, user makes the kickoff call.

---

## When something goes wrong

- **Linear API key unset:** `varlock load 2>&1 | grep LINEAR` — if missing, ask user to set `LINEAR_API_KEY`.
- **`org` not on PATH:** workspace isn't set up. Report and stop.
- **`$LINEAR_HANDLE` unset:** `org worktree create` will refuse with a clear message. Set it in shell rc.
- **Worktree create refused (existing claim):** another dev has the ticket. Don't `--force` without their go-ahead.
- **Ticket id format wrong:** `org worktree create` validates the ticket id format; report and ask.
- **Atlas node missing for a label:** label is wrong or atlas stale. Report; don't guess a replacement.
- **`complexity:high` and grill artifact missing at step 6:** STOP. The implementer's halt rule will fire anyway — better to surface it here than after a dispatch attempt.
