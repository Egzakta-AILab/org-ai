---
id: pillar.capture
name: Capture
type: pillar
layer: L4
status: shipped
owners: [sam.rivera]
depends_on: []
unlocks:
  - "[[search]]"
  - "[[share]]"
code_refs:
  - notewell/src/capture/
---

## Why it matters

Capture is the entry point for all knowledge in Notewell. Without reliable, frictionless capture, the rest of the product has nothing to work with. Getting content in must feel instant and lossless.

## Current state

Editor-based capture is shipped and covers plain text, markdown, and basic file attachments. Voice and web-clip capture are planned. Tagging is wired to capture but still in design.

## Open questions

- Should capture support offline-first draft buffering before sync?
- How do we handle conflicting edits when two users capture to the same note simultaneously?

## References

- [[sync-strategy]] — governs how captured content is persisted and synced
- [[editor-ux]] — the capture surface
- [[tagging]] — enriches captured content
