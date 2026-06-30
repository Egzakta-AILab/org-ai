# Atlas — the egzakta knowledge graph

The **Atlas** is a typed knowledge graph of the egzakta product, captured as
markdown nodes with structured YAML frontmatter. It lives in this meta-repo at
`atlas/` and is the canonical source. Non-dev teammates read and edit through
Obsidian against a shared cloud mirror that we publish from git (one-way).

## What it captures

Each node is one markdown file. Folders group by type:

| Folder | Type | Meaning |
|---|---|---|
| `pillars/` | pillar | Top-level product surfaces (search, chat, draft, context-board, agents) |
| `platform/` | platform | Shared substrate (auth, storage, retrieval-engine, connectors, …) |
| `capabilities/` | capability | Features inside pillars (hybrid-retrieval, reranking, chat-streaming, …) |
| `ops/` | ops | Cross-cutting operational concerns (observability, evals, devops-envs, …) |
| `experience/` | experience | UI/UX patterns (citations-ux, command-palette, …) |
| `commercial/` | commercial | Pricing, licensing, SLA tiers, hw sizing |
| `keystones/` | keystone | Architectural decisions with trade-offs (graphrag variant, parsing strategy, …) |
| `personas/` | persona | Client archetypes and the nodes they light up |
| `milestones/` | milestone | Cycle-bound goals |
| `refs/` | — | Free-form indexes (to-papers, to-competitors, to-code, …); not loaded as nodes |
| `research/` | — | Long-form research docs; not loaded as nodes |

Frontmatter carries the structure: `id`, `type`, `layer`, `status`, `owners`,
`depends_on`, `unlocks`, `code_refs`, `external_refs`, `metrics`, `linear`. See
`atlas/ontology.md` for the full schema.

## Two-tier access

The atlas is consumed by two very different audiences, so it has two access tiers:

**File tier — headless, deterministic.** Python reads the markdown on disk. Used
by `org atlas` commands, by CI checks, and by agents that run without a GUI.
This is the backbone — everything that needs to be reproducible goes through it.

```bash
org atlas list --type capability --status shipped
org atlas show capability.search.hybrid-retrieval
org atlas validate                    # exit 0 on warnings only
org atlas validate --strict           # exit 1 on any issue
org atlas drift                       # is the atlas still in sync with reality?
org atlas drift --json                # machine-readable; for agents and scripts
```

### `validate` vs `drift`

Two distinct checks that share output style but answer different questions:

| Command | Answers | Cadence | Speed |
|---|---|---|---|
| `org atlas validate` | Is the atlas internally consistent? (parses, schema-correct, no broken wikilinks or cycles) | Pre-commit; CI on `atlas/` changes | Fast (~50ms) |
| `org atlas drift` | Is the atlas still in sync with external reality? (code, Linear, calendar) | On-demand; scheduled weekly | Seconds to ~15s (depends on Linear API latency) |

### `drift` axes

`drift` runs three independent axes. Scope with `--axis code,linear,content`; default runs all three.

- **`code`** — walks node-worthy code dirs in each active repo (notewell backend `core/` / `routes/` / `database/`, frontend `features/`, `infra/*`); flags any path no atlas node references via `code_refs:`. The coverage rule is exact-or-descendant only: a `code_refs:` entry pointing at an umbrella dir doesn't silently cover every subdir under it (that was the audit-flagged `platform.storage` bug).
- **`linear`** — for each node with `linear.*` populated, calls Linear's GraphQL API to verify project + initiative IDs still resolve. Maps atlas `status:` (shipped/stable → completed, wip → started, etc.) to Linear's project state; flags mismatches. Inverse sweep: lists active projects with no atlas node referencing them. Requires `$LINEAR_API_KEY` — if unset, the axis emits one `linear-api-key-missing` info finding and skips (useful in CI where the key isn't always available, e.g. fork PRs).
- **`content`** — regex-based body-text heuristics. `aspirational-shipped` (status `shipped`/`stable` + plan-to / TODO / blocked language in body), `calendar-decay-week` (week-N references near action-plan / cycle vocabulary), `calendar-decay-cycle` (a node calls cycle N "active" but the milestone's `end_date` is in the past). Cross-node fact-conflict detection (Postgres 16 vs 18, three different LLM model claims) is **not** included — needs semantic analysis, deferred to a future LLM-assisted axis.

### Pre-commit hook

Block commits that break atlas validation. One-time install per clone:

```bash
ln -sf "$(pwd)/org/scripts/atlas-pre-commit.sh" .git/hooks/pre-commit
chmod +x .git/hooks/pre-commit
```

The hook runs `org atlas validate --strict` only when staged changes touch `atlas/*.md`. Other commits pass through immediately. Bypass intentionally with `git commit --no-verify` — don't make it routine.

### Scheduled drift reports

`.github/workflows/atlas-drift.yml` runs the detector:

- **Mondays 11:17 UTC** — full weekly sweep against `main`, uploads `drift-report.json` as a workflow artifact (30-day retention).
- **On PRs touching `atlas/` or the detector code** — runs against the PR's state, posts a comment with finding counts grouped by axis and code. Subsequent runs on the same PR update the existing comment rather than spamming.
- **`workflow_dispatch`** — kick off manually from the Actions tab.

Set the `LINEAR_API_KEY` repo secret to enable the linear axis in CI. Without it, the workflow still runs but the linear axis emits one info finding and skips.

**Live tier — Obsidian + `obsidian-cli` skill.** When you have Obsidian open on
the shared cloud mirror (so non-dev teammates can browse and edit), the `obsidian-cli`
skill talks to the running app over IPC for interactive search, outlines, and
graph queries. **GUI-bound** — it won't help in CI/hooks/headless agent loops.
That's by design.

## Editing workflow

1. **Dev edits (recommended for code-coupled changes — code_refs, linear ids,
   structural updates):** edit `atlas/*.md` in git, run
   `org atlas validate` to catch breakage, commit, push, then publish to the
   shared mirror so non-dev teammates see the update.

2. **Non-dev edits (recommended for prose, prioritization, fresh ideas):** edit
   through Obsidian against the shared cloud mirror. Tell a dev when you're done — they
   pull your edits from the mirror back into git, validate, commit. (The mirror is
   a one-way copy; capturing non-dev edits is the dev's responsibility.)

## Publishing to a shared mirror

The atlas is git-canonical. The shared mirror is overwritten on each publish.
Always dry-run first. Set `$ATLAS_PUBLISH_TARGET` in your shell rc once (see
[setup.md](setup.md)) pointing at your local mount of the shared cloud folder.
Typical path on macOS: `~/cloud-mirror/notewell/atlas`.

```bash
if [ -z "${ATLAS_PUBLISH_TARGET:-}" ]; then
  echo "ERROR: \$ATLAS_PUBLISH_TARGET is not set. See docs/setup.md." >&2
  exit 1
fi

# Dry-run — review the diff.
rsync -an --delete \
  --exclude '.obsidian/' --exclude 'items/' --exclude '.DS_Store' \
  atlas/ "$ATLAS_PUBLISH_TARGET"/

# Real publish.
rsync -a --delete \
  --exclude '.obsidian/' --exclude 'items/' --exclude '.DS_Store' \
  atlas/ "$ATLAS_PUBLISH_TARGET"/

# Mark the mirror copy so confused teammates can see what's authoritative.
date -u +"Published from git @ %Y-%m-%dT%H:%M:%SZ ($(git rev-parse --short HEAD))" \
  > "$ATLAS_PUBLISH_TARGET/LAST_SYNC.txt"
```

`--delete` is intentional: anything that disappears from git disappears from the
mirror. That's what keeps git canonical.

If publishing becomes a daily chore, wrap this in `org atlas publish` — but until
then the explicit rsync command makes it impossible to publish accidentally.

## What's NOT in git

The `.gitignore` selectively excludes three things under `atlas/`:

| Excluded | Why |
|---|---|
| `atlas/.obsidian/` | Per-user vault state (workspace layout, cursor positions). Regenerated on first open. |
| `atlas/items/` | Autogenerated browser pages from `b2b-ai-platforms/results/*.json`. Drifts on every research refresh; regenerated locally via `atlas/scripts/generate_items.py` (script port is a follow-up). |
| `atlas/scripts/` | Python helpers that depend on sibling repos not in the workspace manifest. Separate PR to untangle imports and bring in-tree. |

If you need the items or scripts dirs today, they're still in the shared mirror copy.

## Validation rules

`org atlas validate` checks the graph for two classes of problems:

**Errors (exit 1 in lenient mode):**
- `duplicate-id` — two nodes claim the same `id:`
- `missing-id` / `missing-name` / `missing-type` — required frontmatter field absent
- `missing-frontmatter` — node-folder file with no `---` block

**Warnings (exit 0 in lenient, exit 1 under `--strict`):**
- `broken-code-ref` — a `code_refs:` entry doesn't resolve under the workspace root
- `unknown-type` — `type:` is not in the known set
- `missing-status` — operational nodes (capability/platform/ops/…) without a `status:`
- `dangling-wikilink` — body `[[link]]` doesn't match any known node, alias, or refs/research doc

Lenient by default because code_refs drift constantly (referenced repos move files
around). Strict for CI gates if and when we add them.

## Next steps

- **Port `atlas/scripts/`** into the in-tree workflow once `b2b-ai-platforms/`
  dependency is untangled.
- **Wrap publish** into `org atlas publish` if the rsync becomes a chore.
- **Auto-regenerate `items/`** from the latest research as part of `org atlas`
  rather than a standalone script.
