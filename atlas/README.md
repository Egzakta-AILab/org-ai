# Notewell Atlas

Internal knowledge base for the Notewell product. A node-per-topic graph that stitches together pillars, platform, capabilities, ops, keystones, personas, and references to code / papers.

Audience: the Notewell team. Not customer-facing.

> **Canonical source: this git directory** (`atlas/`). The optional one-way mirror at `~/cloud-mirror/notewell/atlas` is for non-dev teammates browsing in Obsidian — edits there will be overwritten on the next `rsync` publish. Use Obsidian against the mirror for browsing/reading; make structural edits in git.
>
> For headless reads (CI, agents, scripts), use `org atlas list|show|validate` instead of `obsidian-cli` — it doesn't need a running Obsidian app. Full operational guide: [docs/atlas.md](../docs/atlas.md).

## How to navigate

- Start at [[ontology]] to understand entity types and how nodes link.
- Browse layers:
  - `pillars/` — the product pillars (L4)
  - `platform/` — shared substrate (L2)
  - `capabilities/` — features inside pillars (L3)
  - `ops/` — cross-cutting operational concerns (L1)
  - `experience/` — UI/UX patterns (L5)
- Browse forks:
  - `keystones/` — architectural decisions with trade-offs
  - `personas/` — client archetypes and the nodes they light up
- Follow external references:
  - `refs/to-github.md`

## Tree view

Open Obsidian's graph view to see `depends_on` / `unlocks` edges. The machine-readable form lives in `tree.yaml`.

## Status lifecycle

`research → planned → wip → shipped → stable → deprecated`

## Conventions

- One file per node. Folder = layer.
- Frontmatter `id:` is canonical (dotted form); filename is short kebab-case.
- Wikilinks in frontmatter use quoted `"[[name]]"` so they register in graph view.
- Each node owns its "why" and "current state"; everything else links out.

## Opening as an Obsidian vault

This folder is a standalone vault. In Obsidian: **Open folder as vault** → select `atlas/`. First open will create `.obsidian/` (gitignored — per-user state).

## Headless reads

```bash
org atlas list --type capability --status shipped
org atlas show capability.search.full-text-search
org atlas validate
```

See [docs/atlas.md](../docs/atlas.md) for the two-tier model, publish workflow, and validation rules.
