# Egzakta Workspace Platform — Design

> A lightweight internal developer platform for multi-repo, AI-assisted engineering.

| | |
|---|---|
| **Status** | Phase 1 shipped — six components × three tools, cross-tool parity, atlas in-tree |
| **Owner** | Principal Architect (Platform) |
| **Last updated** | 2026-05-27 |
| **Scope** | The `egzakta/` workspace and every repository it contains |

---

## 1. Summary

Turn `egzakta/` from a folder of independent repos into a thin meta-repository that versions one orchestration layer. The code repos stay independent (gitignored clones). Four layers sit on top: a **manifest** (`repos.yaml`) describing every repo, a **platform layer** (`platform/`) holding shared agents / skills / hooks / standards, a **propagation model** that projects assets into repos without manual duplication, and an **`org` CLI** that runs across repos. Above them all sits the **Atlas** — a typed product knowledge graph — as the semantic layer linking capabilities to code, work tracking, and research.

---

## 2. Motivation

- **`egzakta/` is not a repository today.** It's a directory; the surrounding git root is the user's home. Repos inside (`notewell`, `infra`, `legacy-wiki`, `search-lab`, …) are independent clones with no shared parent.
- **The platform already exists — in one repo.** notewell carries a sophisticated `.claude/` setup: orchestrator + parallel reviewer fan-out + TDD implementer + consolidator + six specialised reviewers. None reusable outside notewell.
- **Standards drift elsewhere.** Other repos have no equivalent of notewell's agents and no shared hook library.
- **No cross-repo operations.** No way to run a command/check/AI task across repos; no machine-readable description of how repos relate (e.g. notewell's integration tests depend on `infra` services).
- **A rich knowledge graph is stranded.** An Obsidian "Atlas" describes the product as a typed graph with `code_refs` and work-tracking IDs — but it lives outside the workspace, so those references don't resolve, and it's under-used.


---

## 3. Goals & non-goals

**Goals**

- Treat all repos as one logical system: shared standards, AI-agent behaviour, workflows.
- Central platform layer: coding rules, reusable AI skills, prompt templates, shared tooling.
- Workspace orchestration: run commands across repos, sync configs, model repo dependencies.
- Skill-based development: small, composable skills instead of large bespoke prompts.
- Developer CLI: `org install`, `org clone`, `org status`, plus cross-repo branch/test helpers.
- The Atlas as a daily, living part of the workflow.

**Constraints**

- No duplicated logic across repos — shared assets have a single source of truth.
- Each repo stays fully usable when cloned and opened on its own.
- Optimise for AI coding agents working across repositories.
- Minimise context overhead while preserving consistency.

**Non-goals**

- No monorepo — repos aren't merged; histories stay separate.
- No forced re-tooling of non-engineering teammates.
- Not a replacement for CI/CD or work tracking — the platform integrates, doesn't replace.

---

## 4. Architecture

Mechanical layers describe *how* work is done; the semantic layer describes *what* is being built and *why*.

```
egzakta/                         meta-repo (git-tracked)
├── atlas/            ── SEMANTIC ── capabilities ↔ code ↔ tracking ↔ research  (the "why")
├── platform/         ── PLATFORM ── standards, agents, skills, hooks, prompts   (the "how")
├── org/  repos.yaml  ── ORCHESTRATION ── CLI + manifest + dependency graph      (the "where")
├── CLAUDE.md  AGENTS.md  docs/   ── workspace router + tool-agnostic standards + setup
│
├── notewell/     (gitignored) ── independent clone
├── infra/        (gitignored) ── independent clone
├── legacy-wiki/  (gitignored) ── independent clone
└── search-lab/   (gitignored) ── independent clone
```

- The meta-repo versions only the orchestration layer. Code repos are gitignored clones — independent.
- `repos.yaml` is the single canonical description of which repos exist and how they relate.
- Atlas `code_refs` (capability → code path) and manifest `depends_on` / `provides` (repo → infrastructure) are two halves of one dependency graph, joined on the repo name.

---

## 5. Meta-repo & manifest

Code repos live inside `egzakta/` as gitignored, independent clones. Submodules rejected — pinned SHAs and detached-HEAD workflows are hostile to both agents and day-to-day development.

`repos.yaml` describes every repo, its tags, dependencies, and platform opt-ins. Single source for `org clone`, `org install`, and any human-readable repo index.

```yaml
version: 1
repos:
  notewell:
    url: https://github.com/your-org/notewell
    tags: [active, backend, frontend]
    depends_on: [infra]
    sync: [agents, standards, hooks]
  infra:
    url: https://github.com/your-org/infra
    tags: [infra]
    provides: [postgres, nats, storage]
  legacy-wiki:
    url: https://github.com/your-org/legacy-wiki
    tags: [archive]
  search-lab:
    url: https://github.com/your-org/search-lab
    tags: [research]
```

- `tags` drive selection (`org run --tags backend`).
- `depends_on` / `provides` encode the cross-repo dependency graph.
- `sync` is the **opt-in** list of platform assets a repo pulls — primary lever for minimising context overhead.

---

## 6. Platform layer

`platform/` is the single source of truth for the six rendered components plus per-tool render profiles:

```
platform/
├── tools/                      per-tool profiles (claude.yaml, cursor.yaml, droid.yaml)
├── agents/<repo>/              tool-agnostic agent sources (_shared/ for cross-repo)
├── standards/<repo>/           single source → CLAUDE.md + AGENTS.md
├── commands/<repo>/            aliases.yaml + per-command override .md files
├── rules/<repo>/*.mdc          code-convention rules (Cursor .mdc; engine translates)
├── hooks/<repo>/               hooks.yaml + scripts/*.sh (per-tool settings merge)
└── skills/                     index.yaml + patches/ + vendor/
```

| Component | What | Renders to |
|---|---|---|
| **agents** | Sub-agent definitions | `.claude/agents/`, `.cursor/agents/`, `.factory/droids/` |
| **standards** | Coding/operating conventions | `CLAUDE.md` (Claude), `AGENTS.md` (Cursor + droid) |
| **commands** | Slash commands (overrides > 1:1 wrappers > aliases) | `.claude/commands/`, `.cursor/commands/`, `.factory/commands/` |
| **rules** | Code-convention rules with file-pattern scopes (Cursor `.mdc` source; engine translates) | `.cursor/rules/`, `.claude/rules/`, `.factory/rules/` |
| **hooks** | Shell scripts on tool events; engine merges bindings into per-tool settings | `_org/` in each tool's hooks dir |
| **skills** | Reusable agent capabilities (`reference` clones or `vendor` copies) | per-tool skills dir (project or global) |

Workspace root also hosts `CLAUDE.md` / `AGENTS.md`, `atlas/` (§10), and `docs/`. See [`platform/README.md`](../platform/README.md) for authoring details. Phase 1 lifted the proven notewell platform; per-repo generalization happens as more repos adopt the components.

---

## 7. Propagation model

Shared assets reach repos through three channels:

| Channel | Destination | Used for | Mechanism |
|---|---|---|---|
| **Global** | `~/.claude/skills/`, `~/.cursor/skills/`, `~/.factory/skills/` | Generic skills usable in any session (Linear, atlas, obsidian-cli) | `org install --global --component skills` |
| **Repo-scoped** | each repo's `.claude/`, `.cursor/`, `.factory/` | Shared agents/standards/commands/rules/hooks a repo opts into | `org install` **renders** them per tool with a "do not edit — edit the source" marker; hooks additionally **merge** bindings into per-tool settings (preserving user entries via `__org_managed__` tag) |
| **Repo-local** | the repo | Repo-specific config | Left untouched; install never overwrites |

**One source, many tools.** The platform stores one tool-agnostic source per asset plus a per-tool profile (`platform/tools/<tool>.yaml`) capturing the deltas — output directory, frontmatter shape, body-token values. `org install` renders source × profile into each tool's native file. The per-tool copies are *generated*, never hand-maintained.

**Why generated files (not symlinks).** Generated, committed files work when a repo is opened on its own; symlinks are fragile on Windows and `@import` paths break standalone. Drift detectable via `org install --check` — CI-ready.

**Minimising context.** Opt-in per repo (`sync:`) pulls only what's needed; skills load on demand; a thin root `CLAUDE.md` routes to detail rather than inlining it.

---

## 8. The `org` CLI

Built in Python with Typer, packaged so `org` is on `PATH`. Matches the workspace stack; trivial to shell out to git and to headless agent invocations.

| Command | Purpose | Status |
|---|---|---|
| `org clone` | Clone or pull every repo in `repos.yaml` | shipped |
| `org install [...]` | Render/install platform assets. Components: `agents`, `standards`, `commands`, `rules`, `hooks`, `skills`. `--check` for CI drift; `--dry-run` plans without writing. Full flag set in [`org/README.md`](../org/README.md). | shipped |
| `org status` | Per-repo git state + workspace hygiene warnings | shipped |
| `org atlas {list,show,validate}` | File-tier reader for the knowledge graph (§10) | shipped |
| `org run "<task>" --tags <sel>` | Headless coding-agent task across selected repos | planned |
| `org exec -- <cmd>` | Plain shell command across selected repos | planned |
| `org branch <name> --tags <sel>` / `org test --tags <sel>` | Cross-repo branch / test helpers | planned |

- Selection is by tag or explicit repo list, derived from the manifest.
- Hygiene gates: `org install --check` and `org atlas validate --strict` both exit non-zero in CI on drift/structural errors.
- Cross-repo execution (`run`, `exec`, `branch`, `test`) is Phase 3 — deferred until multiple repos adopt the platform.

---

## 9. Skill-based development

Workflows are small, composable **skills** in `platform/skills/`, projected to repos or installed globally. Single-purpose, composable, reusable across repos, catalogued in [`docs/skills.md`](skills.md).

Two modes (`reference`: clone pinned upstream into destination; `vendor`: copy from `platform/skills/vendor/<name>/`). All three tools share the same `SKILL.md` primitive; only the install path differs. Each registry entry can declare `secrets_env: […]` — the engine **surfaces** required vars in install output but **never reads or copies values**. Idempotency: every managed destination carries an `.org-install-stamp`; `org install --check` reports drift. See [`docs/skills.md`](skills.md) for the full mechanics.

---

## 10. The Atlas — semantic layer

The Atlas is a typed product knowledge graph (~200 nodes) modelling the product as:

- **Typed nodes** — pillars, capabilities, platform components, ops concerns, experience/UX, commercial, architectural *keystones* (mutually exclusive forks), client *personas*.
- **Typed edges** — `depends_on`, `unlocks`, `implements`, `competes_with`, `inspired_by`, `lights_up`.
- **Status lifecycle** — `research → planned → wip → shipped → deprecated`.

Each node is one markdown file with YAML frontmatter. Canonical id is dotted (`capability.search.hybrid-retrieval`). Nodes carry `code_refs` (workspace paths into repos), `linear` (initiative/project IDs), `external_refs` (competitors, papers).

**Where it sits.** Above the mechanical layers as the semantic layer. Its `code_refs` plus the manifest's `depends_on` / `provides` form one dependency graph, joined on the repo name.

**Home.** Git-tracked at `egzakta/atlas/` — every `code_refs` path resolves to a real file, architectural decisions get a history. Non-engineering access via one-way publish to the shared cloud mirror.

**Two-tier access.** File tier (`org atlas`, parsing markdown on disk) is the headless backbone — safe in CI, hooks, agent loops. Live tier (Obsidian CLI over IPC) is GUI-bound and can't reliably write structured frontmatter, so **all automation is built on the file tier**; live tier is for interactive vault use only. Full guide: [`docs/atlas.md`](atlas.md).

**Adoption levers.**
- `atlas-context` skill — when an agent edits code under a node's `code_refs`, loads that node's *why* / *key decisions* / *open questions*.
- Drift hook — when code under `code_refs` changes without the node, nudges the author.
- Review surfacing — review agents name the touched Atlas node in their output.
- Status sync — read-only job reconciles work-tracking state with node status.

### `org atlas` commands

| Command | Purpose |
|---|---|
| `org atlas validate` | Every `code_refs` path resolves to a real file in a cloned repo |
| `org atlas sync-tracking` | Reconcile node `status` with work-tracking state (read-only report) |
| `org atlas show <id>` / `refs <id>` | Print a node, or jump to its code |
| `org run … --capability <id>` | Resolve a capability → its `code_refs` → repos, and dispatch a task exactly there |

---

## 11. First vertical slice — pipeline hardening

The first concrete deliverable is **not** the meta-spine — it's a self-correcting agent loop and self-enforcing pipeline in notewell. The per-repo enforcement substrate the platform layer later generalises. Built concretely first to avoid designing the shared abstraction before it's proven.

**Defense-in-depth.** A fast type checker (whole-project check well under a second) makes per-edit and end-of-turn type-checking viable; existing errors absorbed into a committed baseline so gates fire only on new regressions.

| Layer | Trigger | Mechanism |
|---|---|---|
| **Config foundation** | — | Type-checker config + baseline + shared hook library; one source every layer reads |
| **Edit-time** | after each edit | Auto-fix silently (formatter/linter), report type/lint errors so the agent self-corrects in-loop; never blocks |
| **End-of-turn gate** | hand-back | Hard block on infrastructure-free checks only (format, lint, type, unit tests, frontend build) |
| **Test runner agent** | end-of-turn | Agent provisions infrastructure by platform, diff-selects integration tests, triages failures |
| **Git hooks** | commit / push | Auto-fix staged files on commit; heavier checks on push behind env flag |
| **CI** | pull request | Type check + two-tier backend tests (unit always; integration via service containers) |

**Cross-repo seam (notewell ↔ infra).** The test-runner provisions infrastructure that belongs to `infra`. The dependency is recorded in `repos.yaml`; a later phase lets the test-runner resolve infrastructure through the manifest.

**Lift-readiness.** Generic pieces (hook library, test-runner agent) resolve the repo root dynamically — lifting into `platform/` later is copy + manifest entry, not a rewrite.

---

## 12. Cross-cutting concerns

- **Secrets.** API keys for integrations are never printed or embedded. Secret-injection tooling supplies them at runtime; schema files declare required keys without values.
- **Multi-tool support.** Standards live in a tool-agnostic `AGENTS.md` so multiple coding-agent tools share one source.
- **Work-tracking hygiene.** Branches follow `<your-handle>/nw-NNN`. Ticket IDs are not embedded in code or repo docs — deviation notes belong on the ticket. Generated descriptions are self-contained.
- **Team shape.** Mostly engineers plus product/leadership. Engineering-facing assets live in git; the Atlas gets a published read-only view for non-engineers.
- **Context budget.** Opt-in sync, on-demand skills, thin router keep per-session context small while preserving consistency.

---

## 13. Roadmap

| Phase | Scope | State |
|---|---|---|
| **0 — Container** | Meta-repo root (`CLAUDE.md`, `AGENTS.md`, `repos.yaml`, `docs/`); notewell ↔ infra dependency; Atlas git-canonical at `egzakta/atlas/` | done |
| **1 — Extract platform layer** | Lift notewell hooks/agents/standards into `platform/`; build `org install` (`--tool`, `--component`, `--global`, `--check`); add `atlas-context` skill + drift hook on the file tier | done |
| **2 — Pipeline slice in notewell** | Defense-in-depth layers (§11) with generic pieces lift-ready; Atlas-node surfacing in review agents | in flight |
| **3 — Orchestration breadth** | `org run` / `exec` / `branch` / `test`; roll sync out to remaining repos; fold existing skill-generation pipeline in as the generator; Atlas graph renderer | next |

---

## 14. Open decisions

- **`org` implementation language.** Python with Typer recommended (matches stack, easy headless-agent invocation). Alternative: compiled binary for portability.
- **Work-tracking placement.** This platform effort as its own initiative or under Infrastructure alongside the AIOps slice.
- **Atlas publish mechanism.** Exact one-way channel for non-engineers (plain file sync vs native read-only web publish).

---

## 15. Glossary

| Term | Meaning |
|---|---|
| **Meta-repo** | Git-tracked `egzakta/` repository versioning the orchestration layer; code repos live inside as gitignored clones. |
| **Manifest** | `repos.yaml` — canonical description of repos, tags, dependencies, platform opt-ins. |
| **Platform layer** | `platform/` — single source for shared standards, agents, skills, hooks, prompts. |
| **Propagation** | Getting shared assets into repos (global, repo-scoped, or repo-local). |
| **Skill** | Small, composable, reusable unit of agent workflow. |
| **Atlas** | Typed product knowledge graph; semantic layer linking capabilities to code, tracking, research. |
| **Node** | One Atlas entry (one markdown file) with typed frontmatter and a canonical dotted `id`. |
