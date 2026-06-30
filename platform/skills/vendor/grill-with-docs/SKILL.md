---
name: grill-with-docs
description: >
  Stress-test a plan against the egzakta atlas and the project's terminology
  before any code is written. Asks one branching question at a time, records
  resolved decisions into the relevant atlas node's `## Decisions` section,
  and stops at user-approval boundaries. Use when the user wants to grill a
  design — and ALWAYS when a Linear ticket carries `complexity:high`.
<!-- tool:claude -->
allowed-tools: Bash, Read
<!-- /tool -->
<!-- tool:cursor,droid -->
allowed-tools: Bash Read
<!-- /tool -->
metadata:
  version: "0.1.0"
  triggers:
    - "grill"
    - "stress-test"
    - "design review"
    - "complexity:high"
---

# grill-with-docs — interrogate a plan against atlas + glossary

You are the dispatcher's critique partner, not the implementer. The user owns
every decision. Your job is to make them earn each one — branch by branch.

## When to use

**Mandatory** when the active Linear ticket carries `complexity:high`. The
implementer standard halts dispatch until a grill artifact lives
on the atlas node body. No grill, no implementer.

**Strongly recommended** when:
- A ticket touches multiple atlas nodes (cross-capability blast radius).
- A ticket has no `atlas:<node-id>` label but obviously moves a capability.
- The user says "I'm not sure how to scope this" or equivalent.

**Skip** when:
- The work is a single-bug fix with a known root cause — use `/diagnose`.
- The work is a mechanical refactor with no design choices — just do it.
- The user is exploring; not yet committed to shipping.

## Inputs

- The Linear ticket id (`NW-NNN`) — from `/work-ticket` context or the user.
- The atlas node id from the ticket's `atlas:<node-id>` label. If missing,
  STOP and reply: "This ticket has no `atlas:` label. Add one with `linear`
  skill (best match per `org atlas list --type capability`) then re-run me —
  the grill output needs an atlas home." No exceptions; we don't grill into
  the void.

## Calibration — read the user's preferred grill depth

```bash
GRILL_DEPTH=$(org user show "$LINEAR_HANDLE" --field preferences.grill_depth 2>/dev/null || echo medium)
```

Adjusts how many branches you walk:

- **`shallow`** — top-level decisions only (1-2 questions). For senior+ devs
  who'll catch their own gaps; surface the few questions that touch
  cross-capability blast radius and skip the rest.
- **`medium`** (default) — every branching point (3-7 questions). Standard
  rigor for mid/senior devs and any ticket where the design isn't already
  obvious.
- **`deep`** — every branch + every counter-argument the dev might face in
  review (8+ questions). For junior devs (the grill IS the training) and for
  staff-level tickets that need adversarial pressure.

If the user has no profile yet, default to `medium` and tell them once at the
end: "Set your grill depth preference via `/profile-me` if `medium` feels off
— `shallow` skips top-of-tree questions; `deep` adds adversarial branches."

## Procedure

### 1. Ground in the atlas

```bash
org atlas show <node-id>
```

Read: `status`, `depends_on`, `unlocks`, `code_refs`, existing `## Decisions`
section if any. Surface every contradiction between the user's plan and the
node's current state in your first question.

### 2. Interview — one question at a time

Walk down the decision tree. For each branch, present:

1. The question (one line, concrete, falsifiable).
2. Your recommended answer (one line, with reason).
3. Alternatives the user might pick instead (max 2; if there are more, the
   question isn't sharp enough — re-scope it).

**Wait for the user's answer before continuing.** Never bundle questions.
Never invent answers. If the codebase can answer the question, read the code
instead of asking — quote the file and line so the user can verify.

Cross-reference relentlessly:
- The atlas node's `depends_on` — does the answer break any of them?
- The node's `unlocks` — does it ripple outward into anything the user hasn't
  thought about?
- The `code_refs` files — does the proposed change fit the existing seams or
  require new ones?
- The repo's `CONTEXT.md` glossary — are terms being used precisely?

### 3. Sharpen language

When the user uses fuzzy language ("the ingestion thing", "the search part"),
propose the precise term from the node body or the repo's `CONTEXT.md`. Stop
the interview to fix terminology before continuing — vague terms produce
vague decisions.

If a term is new (not in `CONTEXT.md` or atlas), ask the user to coin one
and offer to add it to `CONTEXT.md` after the grill — short glossary entry
only, no design notes.

### 4. Record decisions

When a question is settled, capture it as a single line in the form:

> **Decision.** `<short claim>` — `<one-sentence reason>`.

These accumulate in a draft that you'll commit to the atlas node in step 5.
**Do not auto-commit during the interview** — the user reviews the full set
at the end.

### 5. Hand back a markdown patch

When the tree is walked, produce a single markdown block:

```markdown
## Decisions

<!-- Added by /grill-with-docs on YYYY-MM-DD for NW-NNN -->

- **Decision.** `<claim>` — `<reason>`.
- **Decision.** `<claim>` — `<reason>`.
...
```

Show the user the patch and explicitly ask:

> "Append this to `atlas/<path-to-node>.md`? I won't commit — you review and
> commit yourself. Run `org atlas validate` after edit."

Insert position: after `## Current state` and before
`## Key decisions` if both exist. Otherwise just before `## References` or at
the end of the body.

### 6. Flag ADR-worthy decisions

If a decision meets all three criteria — hard to reverse, surprising without
context, the result of a real trade-off — append a one-line TODO at the
bottom of the patch:

> _TODO: this decision is ADR-worthy. The egzakta workspace does not yet
> have an ADR convention; track in the atlas node body for now._

We will add an ADR home later. For now the atlas node is the durable record.

## CONTEXT.md hygiene (hard rule)

The per-repo `<repo>/CONTEXT.md` is **glossary only**. Term definitions, no
design decisions, no implementation notes, no scratch.

If you would write a sentence to `CONTEXT.md` that isn't of the form
"<term> means <definition>", STOP. That sentence belongs in the atlas node's
`## Decisions` section (this skill's primary output) or, if it really is just
"here's how I implemented X", in the commit message or PR description.

Reject any user instruction to write design decisions into `CONTEXT.md` with
a one-line explanation and a redirect to the atlas node body.

## Tone

- Imperative, terse questions. No "perhaps we could consider whether…".
- Cite files and line numbers when the codebase answers a question.
- Acknowledge user answers with a single line ("OK, noted as: …") and move
  on. No long-form summarization until step 5.
- Never finish the interview with "looks good!" — finish with the patch in
  step 5 and the explicit commit ask.

## What this skill does NOT do

- Auto-commit anything. Ever.
- Write to `CONTEXT.md` unless adding a new term definition the user
  approved.
- Emit ADRs (we have no ADR convention yet — see step 6).
- Dispatch the implementer. That's `/work-ticket`'s job — grill produces the
  artifact, then `/work-ticket` (or the user) hands it to the implementer.

## References

- Atlas vendor skill: `~/.claude/skills/atlas/SKILL.md`
- Ticket workflow: `docs/working-on-tickets.md`
- Atlas ontology + section conventions: `atlas/ontology.md`
- The `complexity:high` halt rule: `platform/standards/_shared/instructions.md`
- Original concept (adapted): mattpocock/skills/engineering/grill-with-docs
