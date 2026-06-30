---
id: persona.solo-user
name: Solo User
type: persona
layer: "—"
status: stable
owners: [sam.rivera]
lights_up:
  - "[[capture]]"
  - "[[editor-ux]]"
  - "[[full-text-search]]"
  - "[[tagging]]"
---

## Why it matters

The solo user is Notewell's primary early adopter: a single person building a personal knowledge base. Satisfying this persona validates core capture and retrieval loops before adding collaboration complexity.

## Current state

Solo-user flows are the best-tested path in the product. Editor, search, and basic tagging cover the core loop. Sync and offline are the main gaps for power solo users.

## Key decisions

- Solo user onboards without inviting a team; workspace is private by default.
- No plan/billing gating for solo use in the initial launch.

## References

- [[editor-ux]] — primary daily surface
- [[full-text-search]] — primary recovery mechanism
- [[tagging]] — primary organisation mechanism
