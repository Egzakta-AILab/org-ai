---
id: platform.sync-engine
name: Sync Engine
type: platform
layer: L2
status: wip
owners: [jordan.lee, alex.kim]
depends_on:
  - "[[storage]]"
  - "[[auth]]"
unlocks:
  - "[[version-history]]"
implements: "[[sync-strategy]]"
code_refs:
  - notewell/src/sync/
  - notewell/src/sync/crdt.py
linear:
  initiative:
    name: "Search"
    id: 00000000-0000-0000-0000-0000000000a1
  projects:
    - name: "Query quality"
      id: 00000000-0000-0000-0000-0000000000b1
---

## Why it matters

The sync engine ensures that edits from multiple clients (or concurrent tabs) converge to a consistent state without data loss. It underpins real-time collaboration and offline-first capture.

## Current state

CRDT merge logic is implemented for plain-text note bodies. Conflict resolution for structured fields (title, tags) is stub-only. WebSocket push to clients is wip. No offline buffering yet.

## Key decisions

- CRDT over OT: see [[sync-strategy]] for the trade-off analysis. CRDT branch chosen for simpler client implementation.
- Merge happens server-side before persistence; clients receive the canonical merged document.

## Open questions

- Do we need a CRDT library or is our note model simple enough for a hand-rolled approach?
- How do we handle large binary attachments in the sync stream?

## References

- [[sync-strategy]] — keystone this implements
- [[version-history]] — persists merged snapshots
- [[capture]] — primary write path through the sync engine
