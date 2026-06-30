---
name: fastcontext
description: >-
  Codebase-exploration subagent. Offloads repo search to a dedicated model,
  returns compact validated file:line citations instead of broad
  grep/glob/read in main context. Run before editing, reviewing, debugging, or
  explaining code you not already sure about. Use instead of manual
  grep/glob/read when answer spans more than one file. When in doubt, run
  fastcontext first.
<!-- tool:claude -->
allowed-tools: Bash(fastcontext *)
<!-- /tool -->
<!-- tool:cursor,droid -->
allowed-tools: Bash(fastcontext *)
<!-- /tool -->
metadata:
  version: "0.1.0"
  triggers:
    - "explore the codebase"
    - "where is"
    - "how does this work"
    - "trace this"
    - "what calls"
    - "fastcontext"
---

# fastcontext — codebase exploration

`fastcontext` is a CLI exploration subagent. Hand it a natural-language query;
it drives Read/Glob/Grep over the repo and returns compact, validated
`file:line` citations. Cheaper than reading the repo yourself — keeps main
context clean.

**Default to fastcontext for codebase exploration.** Not sure of answer → run
it before responding or acting. Read returned citations yourself, then proceed.

## When to use

- Understand code before editing, reviewing, debugging, explaining
- Trace logic across files/layers (request -> handler -> service -> DB)
- Code Q&A: "How X work?", "Where Y defined?", "What calls Z?"
- Map dependencies: what a symbol depends on, what depends on it
- Impact: "What breaks if I change X?"

## When NOT to use

- Already read the exact file this session
- Single obvious grep in one known file
- Pure write/generate, zero exploration

## Usage

### CLI (all tools)

Run from repo root:

```bash
fastcontext -q "your query" --max-turns 8 --citation
```

The workspace installs wrapper scripts that pre-configure the endpoint and
model. See your workspace setup guide for installation details.

<!-- tool:droid -->
### Task tool (Droid)

Instead of the CLI, delegate via the Task tool:
`subagent_type: "fastcontext"`, pass the query.
Returns `file:line` citations.
<!-- /tool -->

### egzakta repos are Python/TS

Model sometimes assumes Go/Java from dir layout. State language in query
("in this Python FastAPI repo, where is ...") to steer it.

### Turn budget

| Query | `--max-turns` |
|---|---|
| Precise lookup (one file) | 4-6 |
| Normal cross-file | 8 |
| Deep trace / architecture | 12 |

## Output

`<final_answer>` block, absolute paths, validated to exist; bad paths filtered:

```
<final_answer>
/abs/path/worker.py:54-314 (NoteWorker: request lifecycle)
/abs/path/router.py:1-80 (APIRouter: route registration)
</final_answer>
```

## Setup

CLI reads repo files locally — no code leaves the machine, only tool-call
decisions go over HTTP. Follow your workspace setup guide for install and
endpoint configuration. `fastcontext` not on PATH or endpoint down → fall
back to manual grep/glob/read, tell the user.
