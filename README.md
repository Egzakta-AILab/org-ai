# org-ai

The **meta-repository** for a multi-repo AI-assisted engineering workspace. It turns a
folder of independent repositories into one logical system — shared standards, shared
AI-agent behaviour, shared knowledge graph, and cross-repo tooling — without merging
anything into a monorepo.

This repo versions only the **orchestration layer** plus the canonical knowledge graph.
The code repos (`notewell`, `infra`, `legacy-wiki`, `search-lab`, …) live inside the
workspace as independent, gitignored clones, so each stays fully usable on its own.

> **New here?** Start with the friendly, step-by-step
> [**onboarding guide**](docs/onboarding.md) — zero to your first ticket in ~15 minutes.

## Quick start

```bash
git clone https://github.com/Egzakta-AILab/org-ai.git egzakta
cd egzakta
uv tool install --editable ./org      # puts `org` on PATH (or: pipx install -e ./org)
org clone                             # clone every repo listed in repos.yaml
org status                            # per-repo git state + workspace hygiene
org install --global                  # workspace-shared assets: skills, /work-ticket, hooks
org install --repo notewell           # render shared agents + standards + commands + rules + hooks
org user init                         # bootstrap your developer profile (then /profile-me in a session)
org atlas list --type capability      # browse the knowledge graph
org atlas drift                       # is the atlas still in sync with code + Linear?
```

Then open a Claude session and run `/work-ticket NW-NNN` to start a ticket.
See the [onboarding guide](docs/onboarding.md) for the gentle walkthrough, or
[docs/setup.md](docs/setup.md) for the full installation reference.

## Layout

| Path | What |
|---|---|
| `repos.yaml` | Canonical manifest — every repo, its tags, dependencies, and which coding tools it gets. |
| `.org-ignore` | Sibling dirs to skip during workspace-hygiene check (personal scratch, vendored refs). |
| `platform/` | Single source of truth for the six rendered components (agents, standards, commands, rules, hooks, skills). |
| `org/` | The `org` CLI (Python / Typer): `clone`, `status`, `install`, `atlas`, `worktree`, `user`. |
| `atlas/` | Typed knowledge graph (pillars, capabilities, platform, ops, experience, commercial, keystones, personas). See [docs/atlas.md](docs/atlas.md). |
| `docs/` | Design, setup, skills catalogue, atlas guide, ticket workflow. |
| `CLAUDE.md` / `AGENTS.md` | Workspace-level agent instructions (when present). |
| `notewell/`, `infra/`, … | Independent repo clones (gitignored, added by `org clone`). |

## How it works

- **One source, many tools.** A coding-agent asset is authored once under `platform/`; `org install`
  renders it into each tool's native files — `.claude/`, `.cursor/`, `.factory/` — and into the
  shared `CLAUDE.md` / `AGENTS.md` standards. Generated files carry a "do not edit — edit the source"
  marker and are detected on drift.
- **Cross-tool parity.** Six components × three tools = 18 surfaces, all driven from the same sources.
  Per-tool quirks (Cursor's plain-markdown commands and flat hook schema, droid's stripped-frontmatter
  rules and PascalCase event names, etc.) are absorbed by per-tool render branches — authors don't
  see them.
- **Manifest-driven.** `repos.yaml` is the single description of the workspace; human-readable indexes
  are generated from it, not maintained by hand.
- **Knowledge-grounded.** The atlas at `atlas/` is git-canonical, queryable headlessly via
  `org atlas`, and consulted by agents through the workflow loop (see `docs/working-on-tickets.md`).
  The drift detector (`org atlas drift`) cross-checks the graph against code, Linear, and the
  calendar so refreshes stay mechanical; a GitHub Action runs it weekly and on PRs touching `atlas/`.
- **Repos stay independent.** Generated files are committed inside each repo, so a repo works standalone.
  The meta-repo's `.gitignore` is **deny-by-default**: only the orchestration layer + atlas content
  are tracked, so workspace secrets and repo clones can never be committed by accident.

## Components × tools at a glance

| Component | claude | cursor | droid |
|---|---|---|---|
| agents | ✅ | ✅ | ✅ |
| standards | ✅ | ✅ | ✅ |
| commands | ✅ | ✅ | ✅ |
| rules | ✅ | ✅ | ✅ |
| hooks | ✅ | ✅ | ✅ |
| skills | ✅ | ✅ | ✅ |

Every component renders to every tool that supports it. See [`org/README.md`](org/README.md)
for the detailed per-tool destination + format table.

## Docs

- [docs/onboarding.md](docs/onboarding.md) — **start here.** Friendly zero-to-first-ticket walkthrough for new developers.
- [docs/setup.md](docs/setup.md) — fresh-machine setup, from `git clone` to first `org install`.
- [docs/workspace-platform.md](docs/workspace-platform.md) — the full design.
- [docs/working-on-tickets.md](docs/working-on-tickets.md) — end-to-end Linear → atlas → branch → PR loop.
- [docs/skills.md](docs/skills.md) — skills catalogue (what's installed, where, secrets needed).
- [docs/atlas.md](docs/atlas.md) — knowledge-graph two-tier access, editing, publishing.
- [org/README.md](org/README.md) — the `org` CLI reference + components/tools matrix.
- [platform/README.md](platform/README.md) — authoring guide for the six components.
