---
name: diagnose
description: >
  Six-phase disciplined debugging for hard bugs and performance regressions
  across the egzakta workspace. Builds a deterministic feedback loop
  first, hypothesises before instrumenting, writes the regression test
  before the fix, and captures the post-mortem in Linear. Use when a bug
  resists a quick patch or the user wants a methodical investigation.
<!-- tool:claude -->
allowed-tools: Bash, Read
<!-- /tool -->
<!-- tool:cursor,droid -->
allowed-tools: Bash Read
<!-- /tool -->
metadata:
  version: "0.1.0"
  triggers:
    - "diagnose"
    - "debug"
    - "investigate bug"
    - "regression"
    - "flaky"
---

# diagnose — disciplined debugging for the egzakta stack

Core principle: **reproduce → minimise → hypothesise → instrument → fix →
regression-test**. Skipping phases produces shotgun debugging — the user
loses the loop and you lose them.

## When to use

- A bug the user has hit twice or can't pin down.
- A test that flakes on CI but passes locally (or vice versa).
- A performance regression with no obvious cause.
- A bug spanning multiple repos (e.g. ingestion pipeline misbehaviour).

**Skip** for trivial syntax/typo bugs — just fix them.

## Phase 1 — Build the feedback loop (most critical)

A fast, deterministic, agent-runnable pass/fail signal IS the loop. If you
can't build one, you can't find the cause reliably. Loop options in
priority order (pick the highest one that fits the symptom):

1. **Failing pytest at the right seam.** Backend: `cd <repo>/backend &&
   uv run pytest path/to/test.py::test_name -x`. Prefer a real integration
   test against the compose stack (run `cd infra && docker compose up -d`
   first) over a heavily-mocked unit test — mocked databases lie.
   Frontend: `cd <repo>/frontend && pnpm test <pattern>`.
2. **`curl`/HTTP script** against the running backend (`uv run uvicorn
   src.main:app` or the compose stack) — captures request/response shape
   and reproduces deterministically.
3. **Playwright headless** for frontend regressions: `cd <repo>/frontend &&
   pnpm playwright test <spec>`.
4. **CLI invocation + fixture + snapshot diff.** Good for ingestion
   pipeline bugs: feed a known document, snapshot the output,
   compare to the bug-trigger document.
5. **Captured trace replay.** MLflow runs capture LLM-call traces — replay
   the request that exposed the bug (`mlflow ui` to find the run id) with
   the same prompt and seed.
6. **Throwaway harness** in a worktree: `org worktree create NW-NNN`
   gives you isolated state; write a one-off `_bug_repro.py` that calls
   the suspect code with a minimal input.
7. **`git bisect run <script>`** when you know it used to work — bisect
   the regression to a single commit.

**Iterate on loop quality.** A 30-second loop that reproduces 100% beats a
5-second loop that reproduces 30%. For non-deterministic bugs, raise
reproduction rate above the debuggability threshold before advancing.

**If no loop is constructible**: STOP. Document the attempts. Ask the user
for guidance — they may know an angle you don't. Never proceed without a
loop you trust.

## Phase 2 — Reproduce

Run the loop. Confirm three things:

1. The failure matches the user's actual symptom (not a similar-looking
   one).
2. The reproduction is consistent OR reproduces at a measured rate.
3. The exact symptom is captured (error message, wrong number, timeout,
   etc.) — not "something fails".

Do not advance until reproduction is solid.

## Phase 3 — Hypothesise

Generate 3–5 ranked, falsifiable hypotheses. Each MUST state:

> "If X is the cause, then changing Y makes the bug disappear (or get worse
> in a predictable way)."

Common failure surfaces to consult before listing hypotheses:
- Recent commits to the affected module — `git log --oneline -20 -- <path>/`
- Recent alembic migrations — `ls <repo>/backend/alembic/versions/ | sort -r
  | head -5` (a schema change often surfaces as runtime weirdness)
- The atlas node `code_refs` for that capability — `org atlas show
  capability.<area>.X` — to find the seam you might be missing
- MLflow recent runs for the affected model — drift in upstream behaviour
  is invisible in your code

Present the ranked list to the user before instrumenting. The user has
domain knowledge you don't — they re-rank or eliminate hypotheses.

## Phase 4 — Instrument

Map each probe to a Phase 3 prediction. Change one variable at a time.

Tool preference (most → least precise):
- `pdb` / `breakpoint()` for backend; React devtools for frontend.
- Targeted logs at the hypothesised seam — tag every debug log with a
  unique prefix so cleanup in Phase 6 is `git grep -l '[DEBUG-a4f2]'` and
  delete. Example: `logger.info("[DEBUG-a4f2] chunk count: %s", len(chunks))`.
- MLflow span instrumentation for LLM-pipeline bugs — wrap the suspect
  call in `with mlflow.start_span(name="bug-probe-a4f2"):` and inspect
  inputs/outputs in the MLflow UI.

For performance bugs: run a profiler (`py-spy record` for backend hot
loops; Chrome devtools for frontend) BEFORE hypothesising — the profile
itself produces the ranked hypotheses.

**Never "log everything and grep".** It produces noise, not signal.

## Phase 5 — Fix + regression test

Sequence (do not skip):

1. Minimise the reproduction to the smallest input that still triggers the
   bug.
2. Write the failing test FIRST — at a correct seam (exercises the bug as
   it occurs naturally, not a contrived scaffold).
3. Verify the test fails with the current code.
4. Apply the fix.
5. Verify the test passes.
6. Re-run the original user scenario to confirm the symptom is gone.

If no correct seam exists for the regression test, document it as an
architectural finding in the Phase 6 post-mortem — the bug exposed a gap
in the test surface that the team should plan to close.

## Phase 6 — Cleanup + post-mortem

Cleanup checklist:
- [ ] Original reproduction no longer triggers the bug.
- [ ] Regression test passes locally AND in `/review`.
- [ ] All debug instrumentation removed (`git grep '[DEBUG-' && git grep
      'bug-probe-' && git grep 'breakpoint()'` — all empty).
- [ ] Throwaway harness files deleted (`_bug_repro.py`, etc.).
- [ ] Commit message names the root-cause hypothesis from Phase 3 (so the
      next person finds your post-mortem in `git log`).

Post-mortem (post on the Linear ticket as a comment):

> ## Post-mortem: NW-NNN
> **Root cause.** <one paragraph>
> **Why it wasn't caught earlier.** <one paragraph>
> **What would have prevented this.** <one bullet list of architectural
> changes, with file paths — these become future tickets if non-trivial>

If the bug touched a file listed in any atlas node's `code_refs` AND the
fix changed how that code behaves, flag the atlas node for refresh — the
SessionEnd ask-once hook (when shipped) will surface this; until then,
add a manual TODO in the PR description.

## What this skill does NOT do

- Skip phases. Six-phase order is the discipline; without it you're
  guessing.
- "Log everything" debugging.
- Submit the fix without a regression test (unless Phase 5 documented
  WHY no correct seam exists).
- Auto-resolve the Linear ticket — that's the user's call after PR merge.

## References

- Per-repo testing standards: `<repo>/CLAUDE.md` or `<repo>/AGENTS.md` (pytest, integration vs unit)
- Atlas node for the affected capability: `org atlas show capability.<area>.<x>`
- `/review` for diff sanity before pushing
- Original concept (adapted): mattpocock/skills/engineering/diagnose
