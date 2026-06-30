---
id: capability.share.version-history
name: Version History
type: capability
layer: L3
parent: "[[share]]"
status: wip
owners: [jordan.lee]
depends_on:
  - "[[sync-engine]]"
unlocks: []
implements: "[[sync-strategy]]"
code_refs:
  - notewell/src/versions/store.py
  - notewell/src/versions/diff.py
linear:
  initiative:
    name: "Search"
    id: 00000000-0000-0000-0000-0000000000a1
  projects:
    - name: "Query quality"
      id: 00000000-0000-0000-0000-0000000000b1
---

## Why it matters

Version history lets users recover deleted or overwritten content and understand who changed what. It is especially important in shared workspaces where multiple editors touch the same note.

## Current state

Snapshot model implemented: each save writes a versioned row. Diff rendering between snapshots is wip. UI for browsing history and restoring a version is not yet started.

## Key decisions

- Snapshot-per-save rather than operational-transform log; simpler to reason about, larger storage footprint.
- Implements the CRDT branch of [[sync-strategy]] — concurrent edits are merged before snapshotting.

## Open questions

- How long to retain snapshots? Per-user setting or workspace policy?
- Should we compact adjacent identical snapshots (no-op saves)?

## References

- [[sync-strategy]] — architectural fork this node implements
- [[sync-engine]] — delivers merged state that version-history persists
- [[storage]] — snapshot rows live in the main database
