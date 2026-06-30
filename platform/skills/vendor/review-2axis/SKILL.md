---
name: review-2axis
description: >
  Two-axis review of the current diff: a Standards sub-agent checks the
  code against documented standards (atlas ontology, _shared + per-repo
  instructions, CLAUDE.md), and a Spec sub-agent checks the diff against
  the Linear ticket + atlas node `## Decisions` + grill artifact. Reports
  are kept deliberately UNMERGED so one axis can't mask the other.
  Coexists with `/review` (the per-repo orchestrator pass) — pick this
  for repos without a specialist reviewer or when a quick 2-view read is enough.
<!-- tool:claude -->
allowed-tools: Bash, Read
<!-- /tool -->
<!-- tool:cursor,droid -->
allowed-tools: Bash Read
<!-- /tool -->
metadata:
  version: "0.1.0"
  triggers:
    - "review-2axis"
    - "two-axis review"
    - "review against spec"
    - "standards review"
---

# review-2axis — workspace-shared two-axis diff review

A diff can pass one axis and fail the other:

- Code that follows every standard but implements the wrong thing →
  **Standards pass, Spec fail.**
- Code that does exactly what the ticket asked but breaks the project's
  conventions → **Spec pass, Standards fail.**

Reporting them separately stops one axis from masking the other.

## When to use

- Working in a repo with no specialist reviewers (infra,
  search-lab, legacy-wiki).
- Quick read on a change where a full multi-reviewer orchestrator
  pass would be heavier than needed.
- The user explicitly wants the two-axis view.

**Use `/review` instead** for changes that touch multiple layers
(backend + frontend + tests) where specialist coverage is available.

## Procedure

### 1. Pin the fixed point

Whatever the user said is the fixed point — a commit SHA, branch name
(usually `main`), tag, `HEAD~5`, etc. Don't be opinionated; pass it
through. If they didn't specify, ask:

> "Review against what — `main`, a branch, or a specific commit?"

Don't proceed until you have it. Capture once:

```bash
DIFF_BASE="<fixed-point>"
git diff "${DIFF_BASE}...HEAD"       # three-dot: compare against merge-base
git log "${DIFF_BASE}..HEAD" --oneline
```

### 2. Identify the Spec source

Order of precedence:

1. **Linear ticket** — extract `NW-NNN` from branch name
   (`<handle>/nw-NNN`); pull via the `linear` skill.
2. **Atlas node** — if the ticket has `atlas:<node-id>` labels, run `org
   atlas show <node-id>` for each. The node's `## Decisions` section is
   the spec for design choices.
3. **Grill artifact** — if `/grill-with-docs` ran for this ticket, the
   decisions are appended to the atlas node body. Pull them.
4. **User-supplied path** — if user passed an explicit spec path,
   prefer it.
5. **No spec found** — note this; the Spec sub-agent will report "no
   spec available" rather than guess.

### 3. Identify the Standards sources

Read every file in this list that exists:

- `<repo>/CLAUDE.md` — per-repo standards
- `platform/standards/_shared/instructions.md` — workspace baseline
- `platform/standards/<repo>/instructions.md` — per-repo overrides
- `atlas/ontology.md` — atlas-node-hygiene standards
- `<repo>/CONTEXT.md` — repo glossary (terminology standard)
- `<repo>/CONTRIBUTING.md` — if present

Machine-enforced standards (lint, type-check, formatter configs in
`pyproject.toml`, `eslint.config.*`, etc.) — note them but don't
re-check; the per-repo reviewer's tooling axis handles that. Your
Standards axis is for guidance the linter can't see.

### 4. Spawn both sub-agents in parallel

Single message with two `Agent` tool calls. Use `general-purpose` for
both.

**Standards sub-agent prompt** — include:

- The full diff command output and commit list.
- The list of standards-source files you found.
- This brief:

  > Read the standards docs. Then read the diff. Report per file/hunk
  > every place the diff violates a documented standard. Cite the
  > standard (file + the rule). Distinguish hard violations from
  > judgement calls. Skip anything tooling enforces. Under 400 words.

**Spec sub-agent prompt** — include:

- The diff command and commit list.
- The pulled Linear ticket body + comments.
- The atlas node body (or grill artifact text) if available.
- This brief:

  > Read the spec. Then read the diff. Report:
  > (a) Requirements the spec asked for that are missing or partial.
  > (b) Behaviour in the diff that wasn't asked for (scope creep).
  > (c) Requirements that look implemented but where the implementation
  >     looks wrong.
  > Quote the spec line for each finding. Under 400 words.

If the spec is missing, skip the Spec sub-agent and note this in the
final report ("no spec available — Spec axis skipped").

### 5. Aggregate

Present the two reports under `## Standards` and `## Spec` headings,
verbatim or lightly cleaned. **Do NOT merge or rerank findings** — the
two axes are deliberately separate so the user can see them
independently.

End with a one-line summary: total findings per axis, and the worst
single issue (if any) flagged.

## Coexistence with `/review`

`/review` runs the per-repo orchestrator (code reviewer, test reviewer, etc.)
in parallel and consolidates. It's repo-specific and more thorough for
that repo's conventions.

`/review-2axis` is workspace-shared and lighter — two parallel
general-purpose sub-agents with the standards-vs-spec split.

You can run both: `/review` for specialist coverage,
`/review-2axis` for the spec-axis cross-check the orchestrator
doesn't explicitly do. Don't dedupe their findings — they're looking
at different things.

## Tone

- The two-axis split IS the deliverable. Resist the urge to write a
  combined "executive summary" — the user reads both axes themselves.
- Cite spec lines and standards rules verbatim. Don't paraphrase.
- "Under 400 words per axis" is a hard limit on the sub-agents — if
  they exceed it, your aggregation chops to fit.

## What this skill does NOT do

- Merge findings across axes.
- Auto-fix anything.
- Replace `/review` for full-spectrum per-repo reviews.
- Run on uncommitted work — push first or the diff base doesn't capture
  your local changes.

## References

- Per-repo orchestrator: e.g. `~/.claude/agents/notewell-orchestrator.md`
  (per-repo install via `org install`)
- Shared standards: `platform/standards/_shared/instructions.md`
- Atlas ontology: `atlas/ontology.md`
- Original concept (adapted): mattpocock/skills/in-progress/review
