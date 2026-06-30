---
description: Workspace-shared standards — the baseline every implementer agent in the egzakta workspace inherits, before per-repo overrides.
---

# {{INSTRUCTIONS_FILE}} — egzakta workspace baseline

This file is the shared baseline for every implementer agent across the egzakta workspace. Per-repo standards (e.g. `notewell/{{INSTRUCTIONS_FILE}}`) layer specifics on top — when they conflict, the per-repo rule wins for that repo.

If you're working in a single repo, also read that repo's `{{INSTRUCTIONS_FILE}}`. If you're working across repos via `/work-ticket`, this baseline is what every per-repo implementer shares.

---

## Workspace identity

The egzakta workspace is a multi-repo organisation managed as a single engineering system. Every repo (notewell, infra, legacy-wiki, search-lab, …) is fully independent and clonable on its own; the meta-repo's `org` CLI, `platform/` shared assets, and `atlas/` knowledge graph hold them together.

You — the implementer agent — operate inside ONE repo's worktree at a time (or several in parallel, one session per repo when the ticket spans repos). Cross-repo coordination is the dispatcher's job, not yours.

---

## Hard rule — atlas-labeled tickets

**A ticket with an `atlas:<node-id>` label requires atlas grounding in the dispatch context. No exceptions.**

This is a precondition, not an aspiration.

- **The dispatcher (the user or orchestrating agent)** MUST run `org atlas show <node-id>` and paste the output into the same turn that briefs you. Don't expect the implementer to remember.
- **You (the implementer)** MUST verify atlas context is present in the briefing turn for any ticket carrying an `atlas:` label. If it's missing, STOP immediately and reply:
  > "This ticket carries `atlas:<node-id>` but I don't see grounding context. Run `org atlas show <node-id>` and paste it back before I proceed."

Either the dispatcher pasted it (good) or the loop halts loudly (also good). Silent drops are unacceptable.

---

## Hard rule — `complexity:high` tickets require a grill artifact

**A ticket with a `complexity:high` label requires a `/grill-with-docs` artifact in the dispatch context. No exceptions.**

The grill artifact lives on the relevant atlas node's body, under a `## Decisions` section (convention: `atlas/ontology.md`).

- **The dispatcher** MUST run `/grill-with-docs` against the ticket and obtain the user's approval of the resulting decisions BEFORE briefing you. The grill produces a markdown patch the user reviews + commits to the atlas node; the dispatch brief then references the committed atlas section.
- **You (the implementer)** MUST verify a grill artifact is referenced in the briefing turn for any ticket carrying `complexity:high`. If missing, STOP immediately and reply:
  > "This ticket carries `complexity:high` but I don't see a grill artifact. Run `/grill-with-docs` and have the user approve + commit the design before I proceed."

This is the lever where AI shifts from "do it for me" to "help me think it through". For junior devs especially — the grill IS the training. The implementer waits.

---

## Hard rule — atlas IDs in code

**Never put a Linear ticket id (`NW-NNN`) into code, docstrings, comments, or repo-level docs.**

Linear ids belong in:
- The PR title / description (auto-linked).
- The branch name (`<your-linear-handle>/nw-NNN` — `org worktree create` produces this).
- Optionally the commit message.

Implementation deviations from the ticket go as comments on the Linear ticket, not in code.

The atlas id (`capability.search.full-text-search`) IS allowed in comments when it clarifies cross-references — it's stable across Linear renames.

---

## Hard rule — explore the codebase with fastcontext

**Always use the `fastcontext` skill to explore the codebase before editing, reviewing, debugging, or explaining code you're not already sure about.**

It offloads search to a dedicated model and returns validated `file:line` citations instead of burning your session's context on broad grep/glob/read. Use it for any question spanning more than one file or following logic across modules ("where is X", "what calls Y", "how does Z work", "what breaks if I change W"). Read the returned citations yourself, then act.

egzakta repos are Python and/or TypeScript — state the language in the query so the model doesn't assume Go/Java from the directory layout.

Skip only when you already read the exact file this session, or a single obvious grep in one known file. If `fastcontext` is missing from your tool's skill list, the workspace isn't fully set up — tell the user to run `org install --global`.

---

## Workflow shape

The canonical ticket loop is documented in `docs/working-on-tickets.md`. Per-repo specifics layer on top. The shared shape:

1. **Pick a ticket** — `linear` skill.
2. **Ground in atlas** — `org atlas show <node-id>` when the ticket carries an `atlas:` label.
3. **Create worktrees** — `org worktree create NW-NNN` (cross-repo aware; soft Linear claim).
4. **Grill if complex** — `/grill-with-docs` when `complexity:high` (mandatory) or when the design is non-trivial (optional).
5. **Implement** — TDD first; the per-repo implementer's standards say how.
6. **Self-review** — per-repo review skill (e.g. `/review`) or the workspace-shared `/review-2axis`.
7. **Push, PR, close the loop** — gh pr create; comment on Linear; update atlas node if behavior changed.

---

## Tone

- Imperative. "Read X. Run Y. Verify Z."
- Cite files and line numbers when stating facts.
- No speculation. If you don't know, say so and ask — don't guess.
- Short. Long-form explanation belongs in PR descriptions, not in code.

---

## When per-repo standards override

When this baseline says one thing and a per-repo `{{INSTRUCTIONS_FILE}}` says another for that repo, the per-repo rule wins for that repo. Examples:

- `notewell`'s implementer standard tightens "TDD first" into a strict red/green/refactor loop with specific tools.
- A future `infra` standard might forbid touching shared infrastructure without a maintainer review.

The baseline is the floor, not the ceiling.

---

## Skills you can rely on (workspace-global)

Installed via `org install --global --component skills`:

- `atlas` — headless atlas reader. Use it before planning; respect what it tells you.
- `linear` — ticket + comment + label I/O.
- `obsidian-cli` — GUI-only companion to atlas. Don't use in automated flows.
- `grill-with-docs` — design grill that writes to atlas node body. Mandatory on `complexity:high`.
- `diagnose` — six-phase debugging. Use for hard bugs and regressions.
- `zoom-out` — atlas-first code map. Use when you're unfamiliar with an area.
- `handoff` — worktree-local handoff doc. Use before stopping.
- `review-2axis` — standards + spec parallel review. Coexists with per-repo reviewers like `/review`.
- `fastcontext` — codebase-exploration subagent; default tool for repo exploration. Returns `file:line` citations. Use before editing/reviewing/debugging unfamiliar code.

If a skill is missing from your tool's skill list, the workspace isn't fully set up — tell the user to run `org install --global`.
