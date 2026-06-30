# org — egzakta workspace CLI

`org` orchestrates the egzakta multi-repo workspace from the meta-repo root. It reads
`repos.yaml` (the manifest) and renders the tool-agnostic sources under `platform/` into
each coding tool's native files, plus syncs upstream skills and consults the in-tree
knowledge graph.

## Install

```bash
uv tool install --editable ./org      # or: pipx install -e ./org
```

This puts `org` on your `PATH`. Run it from anywhere inside the workspace; it locates the
root by walking up to `repos.yaml`.

## Commands

| Command | Purpose |
|---|---|
| `org clone [--repo R] [--tags T] [--dry-run]` | Clone missing repos, fast-forward existing ones. Never clobbers a non-git dir. |
| `org status [--repo R] [--tags T]` | Per-repo git state (branch, working tree, ahead/behind, HEAD). Also surfaces workspace hygiene warnings (unmanaged sibling dirs, broken manifest entries). |
| `org install [--tool …] [--component …] [--repo R \| --tags T \| --global] [--check] [--dry-run]` | Render platform sources into each tool's files, and sync skills. |
| `org atlas {list,show,validate,drift}` | Consult the in-tree knowledge graph (file-tier, headless) and detect drift against code / Linear / calendar. See `docs/atlas.md`. |
| `org worktree {create,list,drop}` | Coordinated git worktrees at `<repo>/.worktrees/nw-NNN/` on `$LINEAR_HANDLE/nw-NNN`, with a soft Linear claim. Auto-detects affected repos from a ticket's atlas labels. |
| `org user {init,show,list,validate}` | Per-developer profiles at `platform/profiles/<handle>.yaml`. `show --field <dotted.path>` is the accessor skills shell out to for calibration. |
| `org version` | Print the version. |

## `org install`

Two kinds of work flow through the same command:

1. **File components** (rendered from `platform/` into a repo) — `agents`, `standards`,
   `commands`, `rules`, `hooks`. Per selected **repo × tool × component**, the engine
   renders the tool-agnostic source through the tool profile and writes it to the location
   that tool auto-loads.
2. **Skill components** (synced from upstream into a tool's skills dir) — `skills`. The
   engine clones each registered skill pinned to its `ref` into the per-tool destination
   (or a shared cache for sub-path skills), applies any declared patches, and runs
   `post_install`. Vendor-mode skills (authored under `platform/skills/vendor/`) are
   copied with drift detection via a content fingerprint.

### Components and tool coverage

| Component | claude | cursor | droid | Source |
|---|---|---|---|---|
| `agents` | `.claude/agents/` | `.cursor/agents/` | `.factory/droids/` | `platform/agents/<repo>/*.md` |
| `standards` | `CLAUDE.md` | `AGENTS.md` | `AGENTS.md` | `platform/standards/<repo>/instructions.md` |
| `commands` | `.claude/commands/` (1:1 wrappers + aliases + overrides) | `.cursor/commands/` (1:1 + aliases + overrides; plain markdown, `$1` args) | `.factory/commands/` (aliases + overrides only — droids invoked as `/<name>`) | `platform/commands/<repo>/{aliases.yaml, <name>.md}` (overrides win > wrappers > aliases) |
| `rules` | `.claude/rules/*.md` (`paths:`) | `.cursor/rules/*.mdc` (`globs:` / `alwaysApply:`) | `.factory/rules/*.md` (stripped frontmatter; `**Applies to**` line) | `platform/rules/<repo>/*.mdc` (Cursor format is the source; engine translates per-tool) |
| `skills` | `~/.claude/skills/` or `.claude/skills/` | `~/.cursor/skills/` or `.cursor/skills/` | `~/.factory/skills/` or `.factory/skills/` | `platform/skills/index.yaml` (registry) + `platform/skills/vendor/<name>/` (authored) |
| `hooks` | `.claude/hooks/_org/*.sh` + `.claude/settings.json` (nested) | `.cursor/hooks/_org/*.sh` + `.cursor/hooks.json` (flat + `version: 1`, camelCase events) | `.factory/hooks/_org/*.sh` + `.factory/settings.json` (nested) | `platform/hooks/<repo>/{hooks.yaml, scripts/*.sh}` (per-repo) + `platform/hooks/_shared/` (user-global on `--global`) |

All three tools converge on a shared cross-tool format where it exists: `AGENTS.md` for
standards (Google/OpenAI/Sourcegraph/Cursor/Factory standard), `SKILL.md` for skills
(Claude-defined, adopted by Cursor in Feb 2026 and by Factory in droid v0.26.0).
For components without a shared format (rules, hooks), the engine translates per-tool —
single source, per-tool render. Tools that lack a surface for a component are gated
automatically based on the per-tool profile.

### Selection

- `--repo R` / `--tags T` pick repos. Default: the repo your cwd is in. Omitted entirely
  for global skills (`--global`).
- `--tool t1,t2` picks tools. Default: the repo's `tools:` from the manifest. Comma-separate
  or repeat the flag.
- `--component c1,c2` picks components. Default: all (`agents,standards,commands,rules,hooks,skills`).
- `--global` installs **workspace-shared** assets at the user level (`~/.<tool>/`) so they
  resolve from any cwd: skills, `_shared/` commands (`/work-ticket`), `_shared/` agents, and
  `_shared/` hooks (the closing-loop `Stop` nudge). `standards` + `rules` have no global
  scope and are skipped with a note. (Hooks install global-only — never also per-repo — so a
  `Stop` hook can't fire twice per turn.)
- `--check` reports drift with a non-zero exit (use in CI).
- `--dry-run` previews the planned actions and stops.

### Examples

```bash
# File components for a repo
org install --repo notewell                       # all notewell tools, all components
org install --repo notewell --tool claude         # claude only
org install --repo notewell --component agents    # just the agents
org install --repo notewell --component hooks     # scripts + settings merge
org install --repo notewell --check               # CI drift guard

# Workspace-shared assets — user-global (resolve from any cwd)
org install --global                                          # skills + /work-ticket + shared agents + hooks
org install --global --component skills                       # just the global skills
org install --global --component commands                     # just /work-ticket + future _shared/ commands
org install --global --component hooks                        # just the closing-loop Stop hook
org install --global --tool claude --check                    # CI drift guard, claude only

# Skills — per-repo project skills (when a repo opts into specific skills)
org install --repo notewell --component skills    # notewell's `skills:` list → notewell/.claude/skills/
```

### Developer profiles + worktrees

```bash
org user init                                  # bootstrap platform/profiles/<handle>.yaml from Linear + git
org user show <handle> --field preferences.grill_depth   # single value (skills shell out to this)
org user list                                  # registered profiles
org worktree create NW-123                   # isolated worktree(s) for a ticket, with a soft Linear claim
org worktree list                              # what's in flight
org worktree drop NW-123                     # clean up (refuses if dirty)
```

## `org atlas`

File-tier reader for the in-tree knowledge graph at `atlas/`. Works headlessly — no
running Obsidian app required. Companion to the GUI-only `obsidian-cli` skill.

```bash
org atlas list                                 # all 70+ nodes
org atlas list --type capability               # filter by type
org atlas list --pillar search                 # filter by pillar
org atlas list --type capability --status shipped
org atlas show capability.search.hybrid-retrieval   # frontmatter + body
org atlas validate                             # exit 0 on warnings; exit 1 on structural errors
org atlas validate --strict                    # promote warnings to errors (use in CI)
org atlas drift                                # is the atlas still in sync with code + Linear + calendar?
org atlas drift --axis code,linear             # scope to a subset of axes
org atlas drift --json --report drift.json     # machine-readable + write to file
```

See [docs/atlas.md](../docs/atlas.md) for the two-tier access model, drift detector axes
(code coverage / Linear / content), the pre-commit hook, the scheduled GitHub Action, and
the publish-to-shared-mirror workflow.

## How it works

`platform/` is the single source of truth:

```
platform/
├── tools/             per-tool profiles (output dirs, frontmatter shape, token values)
├── agents/<repo>/     tool-agnostic agent sources (`_shared/` for cross-repo ones)
├── standards/<repo>/  the single source for that repo's CLAUDE.md + AGENTS.md
├── commands/<repo>/   aliases.yaml + optional <name>.md overrides (win > wrappers)
├── rules/<repo>/      .mdc rules (Cursor format is the source; render translates per-tool)
├── hooks/<repo>/      hooks.yaml + scripts/*.sh (per-tool settings.json merge)
└── skills/
    ├── index.yaml     skills registry — upstreams + refs + patches + post_install
    ├── patches/       overlay patches applied on top of the pinned upstream ref
    └── vendor/        skills we author ourselves (atlas, …)
```

### File-component rendering

Sources use `{{TOKEN}}` placeholders (`{{R}}`, `{{INSTRUCTIONS_FILE}}`, `{{SUBAGENT_DISPATCH}}`,
`{{REVIEW_ENTRYPOINT}}`). The renderer substitutes per profile. Generated files carry a
"do not edit" marker pointing back to their source.

### Commands — three sources, one component

The commands component has three layered sources in priority order:

1. **Override files** at `platform/commands/<repo>/<name>.md` — explicit author intent.
   Win over both wrappers and aliases. Have full YAML frontmatter (`description`,
   `argument-hint`, `allowed-tools`, …); the render branch strips it for Cursor and
   translates `$ARGUMENTS` → `$1`.
2. **1:1 wrappers** — auto-derived. One slash command per agent, pointing at the agent
   file in the active tool's agents dir. Skipped on tools that set
   `commands_only_aliases: true` (droid, since droids are invoked directly as `/<name>`).
3. **Aliases** at `platform/commands/<repo>/aliases.yaml` — explicit non-1:1 entries
   (e.g. `/review-2axis` → `notewell-orchestrator`). Skipped with a warning when an override
   or wrapper of the same name already exists.

### Hooks — script + settings merge

Each repo's hooks live in two parts under `platform/hooks/<repo>/`:

- `hooks.yaml` — tool-agnostic event bindings (canonical PascalCase event names with an
  optional `tools: [...]` filter)
- `scripts/*.sh` — the actual shell scripts (with shebang preserved)

The engine writes scripts to `<repo>/<hooks_dir>/_org/<name>.sh` (engine namespace,
executable). It then **merges** the bindings into the per-tool settings file. The merger
identifies engine-owned entries via the `__org_managed__: true` tag; user-authored hooks
elsewhere are preserved across install runs. Per-tool quirks (Cursor's flat schema +
camelCase events + `version: 1`, vs Claude/droid's nested schema + PascalCase) are
absorbed by a small per-tool render path.

### Skills — reference mode + vendor mode

A **reference-mode** skill is a git clone pinned to a ref:

```yaml
# platform/skills/index.yaml
skills:
  linear:
    mode: reference
    source: https://github.com/wrsmith108/linear-claude-skill
    ref: v3.2.0
    tools: [claude, cursor, droid]
    patches:
      - linear/atlas-labels.patch    # relative to platform/skills/patches/
    post_install: [npm install]
    secrets_env: [LINEAR_API_KEY]    # documentation only — never read or copied
```

A **vendor-mode** skill is authored under `platform/skills/vendor/<name>/` (e.g.
`atlas/SKILL.md`). The engine copies the directory into each per-tool destination,
skipping `.git`, `node_modules`, `.env*`. Drift detection uses a deterministic content
fingerprint of the source dir.

For a direct-clone reference skill (no `sub_path`), the engine clones the upstream, checks
out the pinned `ref` (detached), and — if patches are declared — creates a local
`org-managed` branch on top, applies each patch with `git apply --index`, and commits with
engine-owned author so `git status` stays clean. For sub-path skills, the engine clones to
a shared cache under `~/.cache/egzakta-org/skills/` once and copies the requested
sub-path into each destination (patches not yet supported for this mode).

Each managed destination carries an `.org-install-stamp` (auto-added to `.git/info/exclude`).
`--check` reports DRIFT on a stamp mismatch (config changed), the wrong ref checked out,
uncommitted local edits in the destination, or a vendor content fingerprint mismatch.
When an upstream version bump breaks a patch, the install fails fast with a clear "rebase
`platform/skills/patches/<rel>` against the current upstream and re-run" message.

### Secrets

Skills declare `secrets_env:` for the env vars they need at runtime. The engine surfaces
the list in install output ("secrets required at runtime: …") so you know what to set, but
**never reads or copies secret values**. Configure them through your usual secret manager.

## Internals

```
org/src/egzakta_org/
├── cli.py             Typer app — option parsing + atlas / worktree / user sub-app registration
├── workspace.py       find_workspace_root() — walk up to repos.yaml; .org-ignore loader
├── manifest.py        repos.yaml → Repo / WorkspaceSkills / Manifest
├── profiles.py        platform/tools/*.yaml → Profile (paths + tokens + frontmatter)
├── render.py          render_agent / render_standards / render_command / render_command_override / render_rule
├── skills.py          reference + vendor mode; clone + patches + sync; drift detection
├── hooks.py           hooks.yaml + scripts loader; per-tool settings.json merge (per-repo + global)
├── linear/            Linear GraphQL client (fetch_issue, post_comment, claim helpers)
├── users/             per-developer profile loader + bootstrap (egzakta_org.users)
├── ask/               closing-loop signal engine (signals, memo, skip-cache)
├── atlas/             file-tier reader (model, parser, validate, drift)
└── commands/
    ├── install.py     the engine — builds Actions, dispatches file vs skill vs hooks flows
    ├── clone.py       per-manifest clone / fetch / skip-non-git
    ├── status.py      per-repo git state table + hygiene checks
    ├── atlas.py       `org atlas list / show / validate / drift` subcommands
    ├── worktree.py    `org worktree create / list / drop`
    └── user.py        `org user init / show / list / validate`
```

The closing-loop Stop-hook entrypoint lives at `org/scripts/ask_once.py` (run by
`platform/hooks/_shared/scripts/ask-once.sh`).

See [docs/skills.md](../docs/skills.md) for the live skills catalogue,
[docs/atlas.md](../docs/atlas.md) for atlas operations, and
[platform/README.md](../platform/README.md) for an authoring guide covering all components.
