---
id: pillar.share
name: Share
type: pillar
layer: L4
status: wip
owners: [sam.rivera, jordan.lee]
depends_on:
  - "[[auth]]"
  - "[[storage]]"
unlocks: []
code_refs:
  - notewell/src/share/
---

## Why it matters

Share turns Notewell from a personal tool into a collaborative workspace. Teams need to share notes, grant scoped access, and publish read-only links — without inadvertently leaking private content.

## Current state

Basic link-sharing is wip. Role-based access control schema is designed but not yet enforced in the API. Public read-only publish is planned.

## Open questions

- Should share links be revocable independently of team membership?
- Do we need per-note ACLs or is folder-level permission granularity enough?

## References

- [[auth]] — access control foundation
- [[version-history]] — shared notes need auditable edit history
- [[team-admin]] — persona that primarily drives this pillar
