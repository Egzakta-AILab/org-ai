---
description: Per-repo standards for notewell — layers on top of the workspace shared baseline.
---

# {{INSTRUCTIONS_FILE}} — notewell

Read `platform/standards/_shared/instructions.md` first. This file layers notewell-specific rules on top; when they conflict, this file wins.

---

## Repo identity

`notewell` is the main application repo: Python FastAPI backend, TypeScript React frontend. One team owns it end-to-end. All atlas nodes with `code_refs` pointing into this repo are your responsibility.

---

## TDD first

Write the failing test before any implementation. Red → green → refactor. No exceptions. If a correct seam for the regression test doesn't exist, document why in the PR description as an architectural finding — don't skip the test without a written record.

---

## Simplicity first

Prefer the smallest change that satisfies the ticket. If a simpler implementation exists, write it. Complexity requires a justification in the PR description, not in code comments.

---

## Surgical changes

Touch only files the ticket requires. Refactors unrelated to the ticket scope go in a separate ticket. This keeps diffs reviewable and blame history clean.

---

## Conventions

- **Python**: PEP 8, type hints on all public interfaces, `uv` for dependency management, `ruff` for formatting + lint.
- **TypeScript**: strict mode, no `any`, co-locate tests (`.test.ts`) with source. `pnpm` for package management.
- **Atlas label**: every ticket that ships, modifies, or measures a capability node gets an `atlas:<node-id>` label before dispatch.
- **Self-review before PR**: run `{{REVIEW_ENTRYPOINT}}` before opening a PR. Address all blocking findings; document non-blocking ones in the PR description.

---

## Safety & Permissions

- Never commit `.env` files or credentials. Use the workspace `varlock` tool for secrets.
- Any change to auth, session handling, or data-access code requires a second human reviewer before merge — add `review:security` label on the PR.
- Destructive migrations (column drop, table rename, data backfill) require a `/grill-with-docs` pass regardless of `complexity:` label. Add a rollback plan to the PR description.
- Do not enable or expand permissions beyond what the ticket requires.
