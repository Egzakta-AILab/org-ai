---
name: zoom-out
description: >
  Map an unfamiliar area of the egzakta codebase using the atlas as the
  primary index. Walks the user up one abstraction layer — atlas node →
  code_refs → call sites — and names everything in atlas vocabulary. Use
  when you (or the user) are touching code without a mental model of the
  surrounding capability.
<!-- tool:claude -->
allowed-tools: Bash, Read
<!-- /tool -->
<!-- tool:cursor,droid -->
allowed-tools: Bash Read
<!-- /tool -->
metadata:
  version: "0.1.0"
  triggers:
    - "zoom out"
    - "give me the map"
    - "I don't know this code"
    - "context for"
---

# zoom-out — atlas-first map of an unfamiliar code area

You are operating in an area of the egzakta workspace where the user (or
you) doesn't yet have the model. Go up one abstraction layer and produce
a map. The atlas IS the map — start there.

## Procedure

1. **Identify the capability** the code lives under.

   ```bash
   org atlas list --type capability | rg <hint>   # if the user named one
   # or, given a file path, find which atlas node owns it:
   org atlas list --json | jq '.[] | select(.code_refs[]? | startswith("<repo>/<path>"))'
   ```

   If no atlas node references the code: that's the first finding. The
   area is uncovered by the atlas. Tell the user, suggest the closest
   capability they should backfill into.

2. **Read the node body.**

   ```bash
   org atlas show <node-id>
   ```

   Pull: status, depends_on, unlocks, code_refs, `## Current state`,
   `## Decisions` if any.

3. **Walk the code_refs.** For each path in `code_refs`, give a one-line
   description in atlas vocabulary (not generic CS terms). Example:

   - `notewell/backend/src/search/full_text.py` → full-text-search
     orchestrator: query parsing + index lookup + ranking (per
     `capability.search.full-text-search` body).
   - `notewell/backend/src/search/reranker.py` → result reranker;
     gated by feature flag (see node `## Decisions`).

4. **Trace one level of callers.** For each code_ref, who calls it?

   ```bash
   git grep -l "from search.full_text import" notewell/backend/src/
   ```

   Name each caller in atlas vocabulary too.

5. **Surface dependencies + ripple.** Print the `depends_on` and
   `unlocks` lists from the node. The user needs to know what their
   change could blast.

## Tone

- Terse. The user asked for a map, not a tour.
- Use atlas ids (`capability.search.hybrid-retrieval`) AND file paths —
  both, on the same line.
- No speculation. If the atlas doesn't say it and the code doesn't show
  it, don't assert it.

## When to skip

- The user is doing focused code-style work in a file they wrote
  themselves — don't zoom out unprompted.
- The atlas has zero coverage for the area — say so plainly and ask the
  user whether to backfill or proceed without a map.

## References

- Atlas vendor skill: `~/.claude/skills/atlas/SKILL.md`
- Original concept (adapted): mattpocock/skills/engineering/zoom-out
