---
id: keystone.sync-strategy
name: Sync Strategy
type: keystone
layer: "—"
status: wip
owners: [jordan.lee]
branches: [crdt, ot]
code_refs:
  - notewell/src/sync/
---

## Why it matters

How concurrent edits are merged is one of the most consequential architectural choices for a collaborative notes app. The decision shapes client complexity, server-side merge logic, and the format of the version history. Getting it wrong requires a rewrite of the sync and storage layers.

## Current state

CRDT branch is chosen and partially implemented in [[sync-engine]]. OT branch was prototyped and discarded. This keystone is locked — see Key decisions below.

## Key decisions

- **CRDT chosen over OT.** `CRDT merges are associative and commutative, requiring no server-coordination round-trip per operation` — simpler offline behaviour and fewer failure modes for our note model. OT requires strict ordering guarantees that add server complexity.
- **Server-side merge.** Clients send ops; server applies CRDT merge and broadcasts the canonical result. No peer-to-peer sync in scope.

## Branches

- **crdt** — selected. Implemented in [[sync-engine]], persisted by [[version-history]].
- **ot** — discarded. Prototype removed after evaluation.

## Open questions

- Which CRDT library (if any) or should we hand-roll for our simple note schema?

## References

- [[sync-engine]] — implements the `crdt` branch
- [[version-history]] — stores merged snapshots produced by this strategy
