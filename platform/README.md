# platform — single source of truth for shared engineering assets

`platform/` holds the tool-agnostic definitions of the **six rendered components** —
agents, standards, commands, rules, hooks, and skills — plus the per-tool profiles that
say how to render them. The `org install` command projects these into each repo's native
coding-tool files (or, for skills, into the user's tool-specific skills dir). You edit
assets **here**, once; every tool's copy is generated.

## Layout

```
platform/
├── tools/                       # per-tool profiles (the render deltas)
│   ├── claude.yaml              # → .claude/{agents,commands,rules,hooks}, CLAUDE.md, ~/.claude/skills
│   ├── cursor.yaml              # → .cursor/{agents,rules,commands,hooks}, AGENTS.md, ~/.cursor/skills
│   └── droid.yaml               # → .factory/{droids,commands,rules,hooks}, AGENTS.md, ~/.factory/skills
├── agents/
│   ├── _shared/                 # agents installed into every targeted repo
│   └── <repo>/                  # agents scoped to one repo (e.g. notewell/)
├── standards/
│   └── <repo>/instructions.md   # single source → that repo's CLAUDE.md + AGENTS.md
├── commands/
│   └── <repo>/
│       ├── aliases.yaml         # non-1:1 slash-command aliases (review → notewell-orchestrator)
│       └── <name>.md            # optional per-command OVERRIDES (win over wrappers + aliases)
├── rules/
│   └── <repo>/*.mdc             # code-convention rules (Cursor .mdc shape; engine translates per-tool)
├── hooks/
│   └── <repo>/
│       ├── hooks.yaml           # event bindings (canonical PascalCase event names)
│       └── scripts/*.sh         # the actual shell scripts
└── skills/
    ├── index.yaml               # registry: reference upstreams + vendor entries
    ├── patches/                 # overlay patches applied on top of pinned upstream refs
    └── vendor/                  # skills we author ourselves (atlas/, …)
```

## Authoring sources

### Agents and standards — token substitution

A source is one markdown file with superset frontmatter and a body using `{{TOKEN}}`
placeholders for the spots that differ per tool:

| Token | Renders to | Set by |
|---|---|---|
| `{{INSTRUCTIONS_FILE}}` | `CLAUDE.md` / `AGENTS.md` | profile `paths.instructions` |
| `{{R}}` | `""` (repo-relative) or `"<repo>/"` | profile `repo_relative_paths` |
| `{{SUBAGENT_DISPATCH}}` | each tool's sub-agent dispatch idiom | profile `tokens` |
| `{{REVIEW_ENTRYPOINT}}` | `/review` | profile `tokens` |

Agent frontmatter (superset): `name`, `description`, `model`, `readonly`. Each profile's
`frontmatter.emit` decides which keys appear and how (e.g. cursor adds `model` + `readonly`;
droid folds the description and appends an `Invoke with: /<name>` hint).

### Commands — three layered sources

The commands component has three priority-ordered sources:

1. **Override files** at `platform/commands/<repo>/<name>.md` — explicit author intent.
   Win over wrappers and aliases. Have full YAML frontmatter (`description`,
   `argument-hint`, `allowed-tools`, …); the render branch strips it for Cursor (Cursor
   parses YAML as literal text) and translates `$ARGUMENTS` → `$1` (Cursor's positional
   arg convention).
2. **1:1 wrappers** — auto-derived from `platform/agents/<repo>/*.md`. One slash command
   per agent, pointing at the agent in the active tool's agents dir. Skipped on tools
   that set `commands_only_aliases: true` (droid — droids are invoked directly as
   `/<name>`, so a wrapper would shadow the droid).
3. **Aliases** at `platform/commands/<repo>/aliases.yaml` — explicit non-1:1 entries
   (e.g. `/review` → `notewell-orchestrator`). Skipped with a warning when an override
   or wrapper of the same name already exists.

Per-tool destinations:

| Tool | Path | Format |
|---|---|---|
| Claude | `.claude/commands/<name>.md` | YAML frontmatter + body, `$ARGUMENTS` for args |
| Cursor | `.cursor/commands/<name>.md` | Plain Markdown (no frontmatter), `$1`/`$2` for args |
| Droid | `.factory/commands/<name>.md` | YAML frontmatter + body (Claude-compatible) |

Adding a new agent automatically creates 1:1 wrappers in every supporting tool on the
next `org install`. To author a richer slash command (custom prompt body, frontmatter),
drop a `<name>.md` file under `platform/commands/<repo>/`. To rename an existing agent's
invocation, declare an alias in `aliases.yaml`.

**Example override** — `platform/commands/notewell/work-ticket.md`:

```markdown
---
description: Pick up a Linear ticket end-to-end.
argument-hint: <NW-NNN>
allowed-tools: Bash, Read
---

You are starting work on Linear ticket **$ARGUMENTS**. Run the preflight before
implementing: pull ticket, ground in atlas if labeled, check runtime, branch …
```

### Rules — one source, per-tool format

Source files live at `platform/rules/<repo>/*.mdc` in the Cursor `.mdc` shape
(`description` / `globs` / `alwaysApply`). The renderer translates per tool:

| Tool | Path | Format |
|---|---|---|
| Cursor | `.cursor/rules/<name>.mdc` | Frontmatter preserved byte-for-byte (IS the rule config); marker as YAML comment |
| Claude | `.claude/rules/<name>.md` (2.0.64+) | Frontmatter rewritten: `description` kept, `globs:` → `paths:`, `alwaysApply:` dropped (Claude expresses "always" by omitting `paths:`) |
| Droid | `.factory/rules/<name>.md` | Frontmatter stripped (droid doesn't parse YAML here); `description` becomes H1, `globs` becomes a body `**Applies to**: <globs>` line |

Body tokens (`{{R}}` etc.) substitute on every branch.

### Hooks — scripts + per-tool settings merge

Hooks have two source files per repo:

```
platform/hooks/<repo>/
  hooks.yaml             # canonical event bindings, PascalCase event names
  scripts/*.sh           # the actual shell scripts (with shebang preserved)
```

`hooks.yaml` schema:

```yaml
hooks:
  - event: Stop                          # canonical PascalCase name
    matcher: ""                          # optional; defaults to ""
    script: check-platform-drift.sh      # filename in scripts/
    tools: [claude, cursor, droid]       # optional; defaults to all three
```

The engine writes scripts to `<repo>/<hooks_dir>/_org/<name>.sh` (engine namespace,
executable on write) and **merges** the per-tool bindings into the per-tool settings
file:

| Tool | Hooks dir | Settings file | Schema | Events |
|---|---|---|---|---|
| Claude | `.claude/hooks/` | `.claude/settings.json` | nested `{matcher, hooks: [{type, command}]}` | PascalCase |
| Cursor | `.cursor/hooks/` | `.cursor/hooks.json` (dedicated, not settings) | flat `{command, type, matcher}` + `version: 1` top-level | camelCase (`Stop` → `stop`, `UserPromptSubmit` → `beforeSubmitPrompt`) |
| Droid | `.factory/hooks/` | `.factory/settings.json` | nested (Claude-compatible) | PascalCase |

User-authored hooks in the settings file (entries WITHOUT the `__org_managed__: true`
tag) are preserved across install runs. The merger only touches engine-owned entries.
User-authored top-level fields (`permissions`, `env`, …) are also preserved.

### Skills — directory sync, two modes

A skill is a *directory* of files (`SKILL.md` + optional scripts/docs/deps). Two modes:

- **`reference`** — declare an upstream `source` + `ref` + optional `sub_path` /
  `layout: multi`. The engine clones the upstream pinned to `ref` directly into the
  per-tool destination, or clones to `~/.cache/egzakta-org/skills/` once and copies the
  sub-path from there.
- **`vendor`** — copy from `platform/skills/vendor/<name>/`, excluding `.git`,
  `node_modules`, `.env*`. For skills we author ourselves (`atlas/` lives here).
  Drift detection uses a deterministic content fingerprint of the source dir.

Registry shape:

```yaml
# platform/skills/index.yaml
skills:
  <name>:
    mode: reference                          # or: vendor
    source: https://github.com/owner/repo    # reference only
    ref: v1.2.3                              # tag (preferred) or branch
    sub_path: skills/<name>                  # optional — for nested skills
    layout: multi                            # optional — repo contains skills/<name>/
    tools: [claude, cursor, droid]           # all three consume the same SKILL.md format
    patches:                                 # optional — see below
      - <name>/foo.patch
    post_install:                            # run in dest after checkout
      - npm install
    secrets_env: [SOME_API_KEY]              # documentation only — never copied
```

### Patches — overlay a third-party skill

When an upstream skill is *almost* what we need but missing team-specific guidance
(e.g. the `linear` skill needs to know about our `atlas:<node-id>` label convention),
add a `.patch` file under `platform/skills/patches/<name>/` and list it under
`patches:` in the registry. The engine then:

1. Checks out the pinned `ref` (detached).
2. Creates/resets a local `org-managed` branch on top of it.
3. Runs `git apply --check` for each patch (fail-fast if upstream shifted what we patched).
4. Applies each patch with `git apply --index` and commits it with author
   `org-install <org-install@local>` so `git status` stays clean and drift detection keeps working.
5. Runs `post_install` as usual.
6. Stamps `head=<resolved ref sha>` + patch fingerprint; `--check` walks back
   `len(patches)` commits from `HEAD` and verifies the result matches the stamp.

When upstream bumps and a patch no longer applies, the install errors with a
clear "rebase `platform/skills/patches/<rel>` against the current upstream and
re-run" message — fix the patch in a meta-repo PR, then re-install.

Patches are only supported for direct-clone reference mode (skills cloned straight
into the destination). Sub-path skills are content copies, not git clones, so
overlays for them belong in `vendor` mode.

Opt-in lives in `repos.yaml`:

```yaml
skills:
  global: [linear, obsidian-cli, atlas]   # `org install --global`
repos:
  notewell:
    skills: [linear]                      # `org install --repo notewell` → notewell/.claude/skills/linear/
```

Idempotency: every managed destination carries an `.org-install-stamp` file with the
resolved upstream commit (or vendor fingerprint) and a fingerprint of `post_install`.
`org install --check` reports drift on a stamp mismatch, a wrong checked-out ref, or
uncommitted edits inside the destination.

## Authoring workflow

1. Edit the source under `platform/`.
2. Run `org install --check` from the workspace root to see what would change.
3. Run `org install` to write the rendered files into each repo (or `--global` for skills).
4. Commit the regenerated per-tool files in the target repo on a normal feature branch.

## Note on current scope

The agents, standards, commands, rules, and hooks here are demonstrated with the fictional
`notewell` repo as the per-repo example. Cross-repo generalization — `_shared/` assets,
per-repo standards in additional repos — lands as more repos adopt the platform. All tools
render with repo-relative paths (`{{R}}` = `""`) because the review agents run git
commands that require `cwd` = the repo root.
