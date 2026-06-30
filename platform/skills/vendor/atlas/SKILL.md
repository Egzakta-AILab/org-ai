---
name: atlas
description: >
  Headless reader for the Egzakta product knowledge graph (~60 typed nodes:
  pillars, capabilities, platform, ops, experience, commercial, keystones,
  personas). Use when a Linear ticket carries an `atlas:<node-id>` label, the
  user names a capability or pillar, or you need to know where something lives
  in the system. Skip for code-style, single-bug debugging, or isolated
  refactors — read the code instead.
<!-- tool:claude -->
allowed-tools: Bash, Read
<!-- /tool -->
<!-- tool:cursor,droid -->
allowed-tools: Bash Read
<!-- /tool -->
metadata:
  version: "0.1.0"
  triggers:
    - "atlas"
    - "capability"
    - "pillar"
    - "knowledge graph"
---

# Atlas — Egzakta product knowledge graph

A typed graph of pillars, capabilities, platform layers, ops concerns,
experience patterns, commercial decisions, keystones, and personas. Each node
is one markdown file at `egzakta/atlas/` with YAML frontmatter (`id`, `type`,
`status`, `depends_on`, `unlocks`, `code_refs`, `linear`).

**Headless backbone.** Works in CI, hooks, agent loops, terminal — no Obsidian
required. The companion `obsidian-cli` skill is GUI-only (IPC to a running
app); use it only when interactively browsing the vault.

---

## When to consult

**Always:**
- Ticket carries `atlas:<node-id>` — author saying "this work touches this capability." Run `org atlas show <node-id>` before planning.
- User names a capability or pillar (hybrid retrieval, chat streaming, draft canvas, …). `depends_on` shows what else may move.
- Scoping a feature — check what's already shipped, planned, or deprecated.
- Writing a ticket and need the right `atlas:` label.

**Don't:**
- Pure code-style questions — read the code.
- Single-bug debugging — use the stack trace.
- Refactors that don't change behavior.

---

## Commands

```bash
org atlas list                                       # all nodes
org atlas list --type capability                     # types: pillar, capability, platform, ops, experience, commercial, keystone, persona, milestone
org atlas list --status shipped                      # statuses: research, planned, wip, shipped, deprecated
org atlas list --pillar search
org atlas show capability.search.hybrid-retrieval    # frontmatter + body; suggests closest ids on typo
org atlas validate                                   # lenient — exit 0 on warnings
org atlas validate --strict                          # CI mode — exit 1 on any warning
```

Filters compose with AND. Ids are dotted (`capability.search.hybrid-retrieval`), not bare.

Read from the frontmatter: `code_refs` (implementing files), `depends_on` / `unlocks` (blast radius), `linear` (project/initiative this maps to), `metrics`. The body holds the "why" and "current state."

---

## Updating a node

If your work shifts a node's `status`, `metrics`, or `code_refs`, edit the
markdown directly under `egzakta/atlas/` and run `org atlas validate` before
committing. The atlas is canonical in git; any cloud mirror is read-only —
never edit through `obsidian-cli` in an automated flow.

---

## When something looks wrong

- **"Not found":** ids are dotted — check the closest-3 suggestions the CLI prints.
- **`broken-code-ref` warning:** referenced file moved (update the atlas) or the referenced repo isn't cloned (informational).
- **`org atlas` command missing:** workspace setup hasn't run — `uv tool install --editable ./org` from the meta-repo root.

---

## Reference

- End-to-end ticket workflow: `docs/working-on-tickets.md`
- Operational guide (publish, validation rules): `docs/atlas.md`
- Schema: `atlas/ontology.md`
- Label convention: `atlas:<node-id>` on every ticket that ships/modifies/measures a node — see `~/.claude/skills/linear/docs/labels.md`.
