# Ontology

The Atlas is a graph of typed nodes connected by typed edges.

## Entity types

| Type | Layer | Example |
|---|---|---|
| Pillar | L4 | [[search]], [[capture]], [[share]] |
| Capability | L3 | [[full-text-search]], [[tagging]] |
| Platform | L2 | [[storage]], [[auth]], [[sync-engine]] |
| Ops concern | L1 | [[backups]], [[observability]] |
| Experience | L5 | [[editor-ux]] |
| Commercial | L6 | [[pricing]], [[sla]] |
| Keystone | — | [[sync-strategy]] |
| Persona | — | [[solo-user]] |
| Reference index | — | `refs/to-github.md` |

## Relationships

- `depends_on` — hard prerequisite
- `unlocks` — capability or pillar this enables
- `implements` — concrete realisation of a keystone branch
- `competes_with` — competitor node in external refs
- `inspired_by` — paper or benchmark
- `lights_up` — a persona "allocates" this node (skill-tree metaphor)

## Status lifecycle

`research → planned → wip → shipped → stable → deprecated`

- **research** — under investigation, no commitment yet
- **planned** — committed on the roadmap, not started
- **wip** — in progress; code partial or scaffolding only
- **shipped** — first usable implementation merged. Follow-up Linear projects may still be active.
- **stable** — settled: no active Linear projects, no open architectural questions, body documents the as-built reality
- **deprecated** — retired; kept for history and migrations

`shipped` vs `stable` exists to stop the overloading where a node was both "the thing works in production" and "the design is finished." `shipped` says the first; `stable` adds the second. Promote `shipped → stable` once the open questions are resolved and the Linear initiative quiets down.

The validator (`org atlas validate`) flags status drift: `wip` with no `code_refs:` is a warning (aspirational `wip`); `shipped`/`stable` capability with no `metrics:` is a warning; non-`research` nodes without `code_refs:` are a warning (see Required fields below for type-level exceptions).

## Node schema

Every node file starts with YAML frontmatter:

```yaml
---
id: capability.search.full-text-search
name: Full-Text Search
type: capability            # pillar | capability | platform | ops | experience | commercial | keystone | persona
layer: L3                   # L1-L6 or — for keystone/persona
parent: "[[search]]"        # optional
status: shipped             # research | planned | wip | shipped | deprecated
owners: [jordan.lee]
depends_on:
  - "[[storage]]"
unlocks:
  - "[[tagging]]"
implements: null            # a keystone branch, if applicable
code_refs:
  - notewell/src/search/   # repo-relative; resolved via refs/to-github.md
external_refs:
  competitors: [competitor-a, competitor-b]
  papers: [bm25-survey]
  docs: []
linear:
  initiative:
    name: "Search"
    id: 00000000-0000-0000-0000-0000000000a1
  projects:
    - name: "Query quality"
      id: 00000000-0000-0000-0000-0000000000b1
metrics: [ndcg@10, recall@50]
---
```

### `linear:` schema

Canonical form for both `initiative` and `projects`:

```yaml
linear:
  initiative: { name: "Search", id: "00000000-0000-0000-0000-0000000000a1" }
  projects:
    - { name: "Query quality", id: "00000000-0000-0000-0000-0000000000b1" }
```

String form (`initiative: "Search"`, `projects: ["Name"]`) is **no longer accepted** — the validator emits a `legacy-linear-shape` error. PR A2 migrated all existing data to dict form via `org/scripts/migrate_linear_shape.py` (one-shot, idempotent). New entries must use the dict form so renames in Linear don't break atlas references — IDs survive renames, names don't.

Reverse linkage (Linear → atlas) uses the `atlas:<node-id>` Linear label — see the linear skill's `docs/labels.md`.

### Required fields

Per-type rules enforced by `org atlas validate`:

| Field | Required on |
|---|---|
| `id`, `name`, `type` | Every node (errors if missing) |
| `status` | `capability`, `platform`, `ops`, `experience`, `commercial`, `milestone` (warning if missing) |
| `code_refs` | Every node with `status` in `{wip, shipped, stable}` except `persona` and `milestone` (warning if empty) |
| `metrics` | `capability` with `status: shipped` or `stable` (**error** if empty) |

`persona` and `milestone` are exempt from `code_refs` (personas are customer archetypes; milestones are time markers). `pillar` and `keystone` nodes carry `code_refs` pointing at the pillar-spanning code or the decision artifact / config / playbook for the keystone branch — but only when `status` is `wip` / `shipped` / `stable`. `planned` and `research` nodes legitimately have no implementation yet.

### Wikilink form

Frontmatter references (`parent`, `depends_on`, `unlocks`) and body links use **file-stem form**: `[[full-text-search]]`, not `[[capability.search.full-text-search]]`. File stems are the stable identifier; node IDs may be restructured. The validator resolves both forms today but only file-stem form survives ID renames cleanly.

### Cycles

`depends_on` is a DAG. The validator detects cycles and emits `dependency-cycle` warnings. If A and B both legitimately need each other, model one direction as `unlocks` instead.

## Body template

```markdown
## Why it matters
2–3 lines on the value this node delivers.

## Current state
2–4 lines on what exists today, honest about gaps.

## Decisions
<!-- Optional. Appended by /grill-with-docs runs for tickets touching this node.
     Each entry: "**Decision.** `<claim>` — `<reason>`." plus a date + ticket id
     in a comment for traceability. -->
- **Decision.** `<short claim>` — `<one-sentence reason>`.

## Key decisions
- Bullet per architectural or product decision made on this node.

## Open questions
- Bullet per unresolved question.

## References
- Links out to [[keystone-*]] if this node is a branch of one
- Links to docs/*.md, code paths, Linear, papers
```

### `## Decisions` section

A growing log of design decisions ratified for this node. Populated by the
`/grill-with-docs` skill (vendored at `platform/skills/vendor/grill-with-docs/`)
when a ticket carries `complexity:high` (mandatory) or when the user opts to
grill any other complex change.

Differs from `## Key decisions`:

- **`## Key decisions`** is the node author's curated summary of the most
  important architectural/product calls. Edited deliberately, infrequent.
- **`## Decisions`** is a chronological log of ratified design choices from
  ticket-driven grill sessions. Append-only (in practice). One entry per
  grill resolution, with a date + ticket id in a comment for traceability.

When `## Decisions` entries crystallise into a load-bearing architectural
call, the node author may promote them into `## Key decisions` and remove
the original entry — keep `## Decisions` from sprawling indefinitely.

`/grill-with-docs` inserts the `## Decisions` block between
`## Current state` and `## Key decisions` if both exist; otherwise
just before `## References`.

## Keystones vs capabilities

A **keystone** is a mutually-exclusive architectural fork (e.g., CRDT *or* OT for sync). A **capability** is a feature (e.g., full-text search, version history). A capability can `implements` a specific keystone branch.

## Ascendancies (deferred)

A persona can have an "ascendancy" — a preset of nodes that light up together (e.g., *Team Admin* lights up auth, observability, backups, share). Stored as presets in `ascendancies/` once we have node density. For now, personas just list nodes in `lights_up`.

## PoE skill-tree mapping

| PoE concept | Atlas meaning |
|---|---|
| Class starting area | Pillar |
| Central hub | Platform layer |
| Small node | Individual capability |
| Notable | Flagship feature (e.g., full-text search, version history) |
| Keystone | Architectural fork with trade-off |
| Mastery | Fine-tuning choice on a cluster (e.g., reranker: provider-a / provider-b) |
| Jewel socket | External ref — paper / competitor / benchmark slotted into a region |
| Ascendancy | Client-type specialization preset |
| Allocated vs unallocated | `stable` / `shipped` (bright) vs `wip` / `planned` (dim) vs `research` (ghost); `deprecated` is greyed out |
