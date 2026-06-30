# Skills catalogue

Reusable, composable units of agent workflow. Generic skills install at the user level and work in any repo; repo-scoped skills project into a specific repo. Both go through `org install --component skills` — `--global` picks the user-level scope.

Opt-in lives in `repos.yaml`:

```yaml
skills:
  global: [linear, obsidian-cli, atlas]    # installed by `org install --global`
repos:
  notewell:
    skills: [linear]                        # installed by `org install --repo notewell`
```

The registry itself is `platform/skills/index.yaml`.

---

## Modes

| Mode | Source | Engine behavior |
|---|---|---|
| `reference` | upstream git repo (+ optional `sub_path`, `layout: multi`) | Clones pinned to `ref` into the destination (or to `~/.cache/egzakta-org/skills/` then copies the sub-path). Nothing committed in this meta-repo. |
| `vendor` | `platform/skills/vendor/<name>/` (in-tree) | Copies directory into each destination, excluding `.git`, `node_modules`, `.env*`. Drift detection via deterministic content fingerprint. |

Pin `ref:` to a tag (`v3.2.0`); pinning `main` means whatever upstream ships at install time. `org install --check` flags stamp mismatches AND `git status` drift inside any managed destination — version bumps require an explicit install.

### Per-tool conditional blocks (vendor skills)

A single vendored `SKILL.md` can carry tool-specific sections via HTML-comment fences. On install, the engine keeps a block only when the destination tool is listed and strips the fences; for other tools the whole block is dropped. Unfenced text installs everywhere. The drift fingerprint hashes the *source*, so the per-tool divergence in the destination is expected and never flagged.

```markdown
<!-- tool:droid -->
### Task tool (Droid)
Delegate via the Task tool: subagent_type "fastcontext".
<!-- /tool -->
```

Tool names are comma-separated and case-insensitive (`<!-- tool:claude, cursor -->`). Reference-mode (upstream-cloned) skills are not post-processed — fences only apply to vendor sources we author.

---

## Registered skills

| Skill | Mode | Source | Ref | Tools | Patches | Secrets |
|---|---|---|---|---|---|---|
| `linear` | reference | [wrsmith108/linear-claude-skill](https://github.com/wrsmith108/linear-claude-skill) | `v3.2.0` | claude, cursor, droid | `linear/atlas-labels.patch` | `LINEAR_API_KEY` |
| `obsidian-cli` | reference (sub-path: `skills/obsidian-cli`) | [pablo-mano/Obsidian-CLI-skill](https://github.com/pablo-mano/Obsidian-CLI-skill) | `main` | claude, cursor, droid | — | — |
| `atlas` | vendor (`platform/skills/vendor/atlas/`) | in-tree | — | claude, cursor, droid | — | — |
| `grill-with-docs` | vendor (`platform/skills/vendor/grill-with-docs/`) | in-tree | — | claude, cursor, droid | — | — |
| `diagnose` | vendor (`platform/skills/vendor/diagnose/`) | in-tree | — | claude, cursor, droid | — | — |
| `zoom-out` | vendor (`platform/skills/vendor/zoom-out/`) | in-tree | — | claude, cursor, droid | — | — |
| `handoff` | vendor (`platform/skills/vendor/handoff/`) | in-tree | — | claude, cursor, droid | — | — |
| `review-2axis` | vendor (`platform/skills/vendor/review-2axis/`) | in-tree | — | claude, cursor, droid | — | — |
| `profile-me` | vendor (`platform/skills/vendor/profile-me/`) | in-tree | — | claude, cursor, droid | — | — |
| `fastcontext` | vendor (`platform/skills/vendor/fastcontext/`) | in-tree | — | claude, cursor, droid | — | — |

**`linear`** — manages Linear issues, projects, initiatives from an agent session. Runs `npm install` as `post_install`. The patch adds an "Atlas Linkage Labels" section to `docs/labels.md`, applied on a local `org-managed` branch on top of `v3.2.0`.

**`obsidian-cli`** — live IPC access to a running Obsidian app (read/write notes, search, list/move/rename, tasks, orphans). Use for vault enrichment when you're at a screen, not for headless automation. Agents needing the atlas in CI/hooks/headless loops use the `atlas` skill (file-tier) instead.

**`atlas`** — teaches agents when and how to consult the in-tree knowledge graph via `org atlas list|show|validate`. Headless backbone — works from any environment without a running Obsidian app. Auto-triggers on prompts mentioning "atlas", "capability", "pillar", "knowledge graph". Standards require atlas grounding for any Linear ticket carrying an `atlas:<node-id>` label. Edit at `platform/skills/vendor/atlas/SKILL.md`, then `org install --global --component skills`.

**`grill-with-docs`** — design grill that interrogates a plan against the atlas + repo glossary one branching question at a time. Mandatory before the implementer dispatches on `complexity:high` Linear tickets — the standard halts dispatch until a grill artifact lives on the relevant atlas node's `## Decisions` section. Produces a markdown patch the user reviews + commits; never auto-commits. adapted from mattpocock/skills/engineering/grill-with-docs.

**`diagnose`** — six-phase disciplined debugging (reproduce → minimise → hypothesise → instrument → fix → regression-test) for hard bugs. References pytest+uv loops, Playwright for frontend, Linear post-mortem comments. adapted from mattpocock/skills/engineering/diagnose.

**`zoom-out`** — atlas-first code map for unfamiliar areas. Walks `org atlas show <node>` → `code_refs` → call sites, naming everything in atlas vocabulary. Falls back to grep only when no atlas node covers the area. adapted from mattpocock/skills/engineering/zoom-out.

**`handoff`** — worktree-local handoff document for the next session. Writes to `<active-worktree>/.handoffs/<ticket>-<iso>.md` (not OS temp) so a session resuming in the same worktree picks it up automatically. Redacts secrets, references PR + Linear + atlas artifacts by URL. adapted from mattpocock/skills/productivity/handoff.

**`review-2axis`** — workspace-shared two-axis review of a diff: Standards sub-agent (vs `platform/standards/`, `CLAUDE.md`, `atlas/ontology.md`) and Spec sub-agent (vs Linear ticket + atlas node `## Decisions` + grill artifact) run in parallel; reports are deliberately UNMERGED so one axis can't mask the other. Coexists with repo-specific reviewer agents (e.g. the notewell 6-reviewer specialist pass) — use review-2axis for any repo or for a quick 2-view read. adapted from mattpocock/skills/in-progress/review.

**`fastcontext`** — codebase-exploration subagent. Agents delegate repo search here — via the `fastcontext` subagent (Task tool) or the `fastcontext` CLI — instead of broad grep/glob/read in the main context. Returns validated `file:line` citations. The standards make it the default for codebase exploration: use before editing/reviewing/debugging unfamiliar code. State the language in the query (the model otherwise guesses Go/Java from directory structure). Edit at `platform/skills/vendor/fastcontext/SKILL.md`, then `org install --global --component skills`.

**`profile-me`** — interview-driven completion of the per-developer workspace profile (`platform/profiles/<short-handle>.yaml`). Bootstrap the identity half with `org user init`, then run `/profile-me` to fill in role, areas, owns, learning, and preferences (grill depth, review style, handoff detail) via a short grilling session. Updates the YAML in place; does NOT auto-commit. Other skills read calibrated preferences via `org user show $LINEAR_HANDLE --field preferences.X` (grill-with-docs → grill_depth, handoff → handoff_detail, repo orchestrators → review_style).

---

## Ops

**Tool coverage.** All three tools (Claude Code, Cursor since Feb 2026, Factory droid since v0.26.0 / Nov 2025) consume the same `SKILL.md` primitive (YAML frontmatter + markdown body). Only the install path differs: `~/.<tool>/skills/<name>/` for global, `.<tool>/skills/<name>/` for project. The engine performs a byte-identical directory sync into each destination.

**Patches** (reference mode only — sub-path and vendor skills use copy semantics, so overlays for them belong in `vendor` mode). Use when an upstream is *almost* what we need but missing team-specific guidance. Add a `.patch` file under `platform/skills/patches/<name>/`, list it under `patches:` in the registry. The engine:

1. Checks out the pinned `ref` (detached).
2. Creates/resets a local `org-managed` branch on top of it.
3. Runs `git apply --check` for each patch (fail-fast if upstream shifted).
4. Applies with `git apply --index` and commits as `org-install <org-install@local>` so `git status` stays clean and drift detection keeps working.
5. Runs `post_install`, stamps `head=<resolved sha>` + patch fingerprint.

When upstream bumps and a patch no longer applies, install errors with a clear "rebase `platform/skills/patches/<rel>`" message — fix the patch in a meta-repo PR, then re-install.

**Secrets.** Skills declare `secrets_env: [VAR_NAME, …]` for env vars needed at runtime. The engine **surfaces** the list in install output so you know what to set, but **never reads or copies secret values**. Configure them through your usual secret manager (`varlock`, direnv, shell rc).

---

## Conventions

- Small and single-purpose — one workflow per skill.
- Composable — higher-level workflows invoke several skills.
- Versioned upstream — pin `ref:` to a tag when the upstream publishes them.

## Roadmap

- `layout: multi` for multi-skill packs (clone once, install each nested skill as its own entry).
- Per-repo skills projection (e.g. `notewell/.claude/skills/`) once a repo has a need not served by the global set.
- Additional vendor skills as patterns emerge.
